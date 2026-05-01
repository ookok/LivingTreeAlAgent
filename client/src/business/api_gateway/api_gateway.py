"""
API网关主类 - API Gateway

功能：
1. 统一API入口
2. 路由分发
3. 系统集成
4. 请求监控
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

from .api_request import APIRequest
from .api_response import APIResponse

logger = logging.getLogger(__name__)


@dataclass
class APIRoute:
    """API路由定义"""
    endpoint: str
    handler: Callable
    description: str = ""
    version: str = "v1"
    requires_auth: bool = False


class APIGateway:
    """
    API网关 - 统一管理所有系统API
    
    核心功能：
    1. 路由注册与分发
    2. 请求日志记录
    3. 统一错误处理
    4. 系统集成
    """
    
    def __init__(self):
        self._routes: Dict[str, APIRoute] = {}
        self._modules: Dict[str, Any] = {}
        
        # 请求统计
        self._request_stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'avg_time': 0.0
        }
        
        # 注册内置路由
        self._register_builtin_routes()
    
    def _register_builtin_routes(self):
        """注册内置路由"""
        # 系统状态
        self.register_route('system/status', self._handle_system_status, 
                          description="获取系统状态", requires_auth=False)
        
        # 系统统计
        self.register_route('system/stats', self._handle_system_stats,
                          description="获取系统统计", requires_auth=False)
        
        # API列表
        self.register_route('api/list', self._handle_api_list,
                          description="获取API列表", requires_auth=False)
    
    def register_route(self, endpoint: str, handler: Callable, 
                      description: str = "", version: str = "v1",
                      requires_auth: bool = False):
        """
        注册API路由
        
        Args:
            endpoint: 端点名称
            handler: 处理函数
            description: 描述
            version: 版本
            requires_auth: 是否需要认证
        """
        self._routes[endpoint] = APIRoute(
            endpoint=endpoint,
            handler=handler,
            description=description,
            version=version,
            requires_auth=requires_auth
        )
        logger.info(f"注册API路由: {endpoint}")
    
    def register_module(self, module_name: str, module_instance: Any):
        """
        注册模块
        
        Args:
            module_name: 模块名称
            module_instance: 模块实例
        """
        self._modules[module_name] = module_instance
        logger.info(f"注册模块: {module_name}")
        
        # 自动注册模块的方法作为API
        self._auto_register_module_methods(module_name, module_instance)
    
    def _auto_register_module_methods(self, module_name: str, module_instance: Any):
        """自动注册模块方法"""
        import inspect
        
        for method_name in dir(module_instance):
            if method_name.startswith('_'):
                continue
            
            method = getattr(module_instance, method_name)
            if callable(method):
                endpoint = f"{module_name}/{method_name}"
                self.register_route(endpoint, method,
                                  description=f"{module_name}模块的{method_name}方法")
    
    def call(self, endpoint: str, **kwargs) -> Dict:
        """
        调用API
        
        Args:
            endpoint: API端点
            **kwargs: 请求参数
        
        Returns:
            响应结果
        """
        start_time = time.time()
        request_id = f"req_{int(time.time() * 1000)}"
        
        try:
            # 查找路由
            route = self._routes.get(endpoint)
            if not route:
                return APIResponse.error(404, f"API端点不存在: {endpoint}", request_id).to_dict()
            
            # 检查认证（简化实现）
            if route.requires_auth:
                if not kwargs.get('auth_token'):
                    return APIResponse.error(401, "需要认证", request_id).to_dict()
            
            # 执行处理函数
            result = route.handler(**kwargs)
            
            execution_time = time.time() - start_time
            
            # 更新统计
            self._update_stats(True, execution_time)
            
            # 包装响应
            if isinstance(result, dict):
                return {
                    'success': True,
                    'data': result,
                    'message': '操作成功',
                    'request_id': request_id,
                    'execution_time': execution_time
                }
            else:
                return APIResponse.success(result, request_id=request_id, execution_time=execution_time).to_dict()
        
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_stats(False, execution_time)
            
            logger.error(f"API调用失败 {endpoint}: {e}")
            return APIResponse.error(500, str(e), request_id).to_dict()
    
    def _update_stats(self, success: bool, execution_time: float):
        """更新请求统计"""
        self._request_stats['total'] += 1
        
        if success:
            self._request_stats['success'] += 1
        else:
            self._request_stats['failed'] += 1
        
        # 更新平均时间
        total = self._request_stats['total']
        self._request_stats['avg_time'] = (
            self._request_stats['avg_time'] * (total - 1) + execution_time
        ) / total
    
    def _handle_system_status(self, **kwargs) -> Dict:
        """获取系统状态"""
        status = {}
        
        # 检查已注册模块状态
        for module_name, module in self._modules.items():
            if hasattr(module, 'get_status'):
                try:
                    status[module_name] = module.get_status()
                except Exception as e:
                    status[module_name] = {'error': str(e)}
            else:
                status[module_name] = {'available': True}
        
        return status
    
    def _handle_system_stats(self, **kwargs) -> Dict:
        """获取系统统计"""
        return {
            'requests': self._request_stats,
            'routes': len(self._routes),
            'modules': list(self._modules.keys())
        }
    
    def _handle_api_list(self, **kwargs) -> Dict:
        """获取API列表"""
        return {
            'routes': [
                {
                    'endpoint': route.endpoint,
                    'description': route.description,
                    'version': route.version,
                    'requires_auth': route.requires_auth
                }
                for route in self._routes.values()
            ]
        }
    
    def get_route(self, endpoint: str) -> Optional[APIRoute]:
        """获取路由定义"""
        return self._routes.get(endpoint)
    
    def get_all_routes(self) -> List[APIRoute]:
        """获取所有路由"""
        return list(self._routes.values())
    
    def get_modules(self) -> Dict[str, Any]:
        """获取所有模块"""
        return self._modules
    
    def start(self):
        """启动API网关"""
        logger.info("API网关已启动")
    
    def stop(self):
        """停止API网关"""
        logger.info("API网关已停止")


# 单例模式
_gateway_instance = None

def get_api_gateway() -> APIGateway:
    """获取API网关实例"""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = APIGateway()
    return _gateway_instance