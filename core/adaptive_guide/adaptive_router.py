"""
自适应功能路由器 - Adaptive Router

核心理念：根据可用配置自动选择最佳实现路径

功能：
1. 检查理想配置
2. 寻找降级方案
3. 启动引导流程
4. 返回执行结果

使用示例：
    router = AdaptiveRouter()
    
    # 执行功能，自动路由
    result = await router.execute_feature("weather_forecast", {"location": "Beijing"})
    logger.info(f"使用方案: {result['implementation']}")
    
    # 检查是否需要引导
    if result.get("requires_guide"):
        guide = router.start_guide(result["feature_id"])
"""

from core.logger import get_logger
logger = get_logger('adaptive_guide.adaptive_router')

import os
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from .downgrade_matrix import DowngradeMatrix, Implementation, AvailabilityLevel, get_downgrade_matrix
from .user_profile_detector import UserProfileDetector, UserProfile, get_user_profile_detector
from .shortest_path_guide import ShortestPathGuide, GuideFlow, get_shortest_path_guide

logger = logging.getLogger(__name__)


class RouteStrategy(Enum):
    """路由策略"""
    PREFER_FREE = "prefer_free"        # 优先免费
    PREFER_QUALITY = "prefer_quality"  # 优先质量
    PREFER_SPEED = "prefer_speed"      # 优先速度
    BALANCED = "balanced"              # 均衡模式


@dataclass
class RouteResult:
    """
    路由结果
    
    Attributes:
        success: 是否成功
        feature_id: 功能标识符
        implementation: 使用的实现ID
        implementation_name: 实现名称
        level: 可用性级别
        requires_guide: 是否需要引导
        guide_flow: 引导流程（如果需要）
        config_keys_needed: 需要配置的配置项
        message: 结果消息
        data: 执行结果数据
    """
    success: bool
    feature_id: str
    implementation: Optional[str] = None
    implementation_name: Optional[str] = None
    level: Optional[str] = None
    requires_guide: bool = False
    guide_flow: Optional[GuideFlow] = None
    config_keys_needed: List[str] = field(default_factory=list)
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    latency_ms: int = 0
    accuracy: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "feature_id": self.feature_id,
            "implementation": self.implementation,
            "implementation_name": self.implementation_name,
            "level": self.level,
            "requires_guide": self.requires_guide,
            "guide_flow_id": self.guide_flow.flow_id if self.guide_flow else None,
            "config_keys_needed": self.config_keys_needed,
            "message": self.message,
            "data": self.data,
            "latency_ms": self.latency_ms,
            "accuracy": self.accuracy,
        }


@dataclass
class FeatureRequest:
    """
    功能请求
    
    描述一个功能调用的完整信息
    """
    feature_id: str
    input_data: Dict[str, Any]
    strategy: RouteStrategy = RouteStrategy.BALANCED
    user_context: Optional[Dict[str, Any]] = None
    callback: Optional[Callable] = None
    timeout: int = 30  # 超时秒数


class AdaptiveRouter:
    """
    自适应功能路由器
    
    核心决策逻辑：
    1. 接收功能请求
    2. 检查理想配置是否满足
    3. 如果满足，执行理想方案
    4. 如果不满足，寻找降级方案
    5. 如果没有可用方案，启动引导
    6. 返回路由结果
    """
    
    _instance: Optional["AdaptiveRouter"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._matrix = get_downgrade_matrix()
        self._profile_detector = get_user_profile_detector()
        self._guide = get_shortest_path_guide()
        
        # 功能注册表: feature_id -> executor_func
        self._executors: Dict[str, Callable] = {}
        
        # 统计信息
        self._stats = {
            "total_requests": 0,
            "successful_routes": 0,
            "fallback_routes": 0,
            "guide_started": 0,
        }
        
        self._initialized = True
        logger.info("AdaptiveRouter initialized")
    
    def register_executor(self, feature_id: str, executor: Callable):
        """
        注册功能执行器
        
        Args:
            feature_id: 功能标识符
            executor: 执行函数，签名: async def(config, input_data) -> dict
        """
        self._executors[feature_id] = executor
    
    async def execute_feature(
        self, 
        feature_id: str, 
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        strategy: RouteStrategy = RouteStrategy.BALANCED,
        user_context: Optional[Dict[str, Any]] = None
    ) -> RouteResult:
        """
        执行功能（主入口）
        
        Args:
            feature_id: 功能标识符
            input_data: 输入数据
            config: 当前配置
            strategy: 路由策略
            user_context: 用户上下文
        
        Returns:
            RouteResult: 路由结果
        """
        start_time = datetime.now()
        self._stats["total_requests"] += 1
        
        config = config or self._get_current_config()
        user_context = user_context or {}
        
        # Step 1: 获取最佳可用实现
        impl = self._get_best_implementation(feature_id, config, strategy)
        
        if impl is None:
            # 没有可用实现，需要引导
            return await self._handle_no_implementation(feature_id, config, user_context)
        
        # Step 2: 检查是否需要配置
        if not impl.is_available(config):
            # 需要配置但未配置，启动引导
            return await self._handle_needs_configuration(
                feature_id, impl, config, user_context
            )
        
        # Step 3: 执行实现
        try:
            result = await self._execute_implementation(impl, config, input_data)
            
            # 路由成功
            self._stats["successful_routes"] += 1
            
            return RouteResult(
                success=True,
                feature_id=feature_id,
                implementation=impl.id,
                implementation_name=impl.name,
                level=impl.level.value,
                message=f"使用 {impl.name} 执行成功",
                data=result,
                latency_ms=self._calc_latency(start_time),
                accuracy=impl.accuracy,
            )
            
        except Exception as e:
            logger.error("Failed to execute %s: %s", impl.id, str(e))
            
            # 尝试降级
            fallback_result = await self._try_fallback(feature_id, config, input_data, strategy)
            
            if fallback_result.success:
                self._stats["fallback_routes"] += 1
                return fallback_result
            
            return RouteResult(
                success=False,
                feature_id=feature_id,
                message=f"执行失败: {str(e)}",
            )
    
    def _get_current_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        # 从环境变量和配置文件获取
        config = {}
        
        # 从环境变量
        for key, value in os.environ.items():
            if key.endswith("_API_KEY") or key.endswith("_TOKEN") or key.endswith("_SECRET"):
                config[key] = value
            elif key.startswith("ECO_"):
                config[key[4:]] = value
        
        return config
    
    def _get_best_implementation(
        self, 
        feature_id: str, 
        config: Dict[str, Any],
        strategy: RouteStrategy
    ) -> Optional[Implementation]:
        """获取最佳实现"""
        prefer_free = strategy in (RouteStrategy.PREFER_FREE, RouteStrategy.BALANCED)
        return self._matrix.get_best_available(feature_id, config, prefer_free)
    
    async def _handle_no_implementation(
        self, 
        feature_id: str, 
        config: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> RouteResult:
        """处理没有可用实现的情况"""
        # 检查是否有降级方案
        fallback_chain = self._matrix.get_fallback_chain(feature_id, config)
        
        if fallback_chain:
            # 有降级方案，使用最低级但可用的
            impl = fallback_chain[-1]
            self._stats["fallback_routes"] += 1
            
            return RouteResult(
                success=True,
                feature_id=feature_id,
                implementation=impl.id,
                implementation_name=impl.name,
                level=impl.level.value,
                message=f"使用降级方案 {impl.name}",
                requires_guide=True,  # 提示用户可以升级
            )
        
        # 没有可用实现，启动引导
        return await self._start_guide(feature_id, user_context)
    
    async def _handle_needs_configuration(
        self, 
        feature_id: str, 
        impl: Implementation,
        config: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> RouteResult:
        """处理需要配置的情况"""
        # 检查是否支持自动配置
        missing_keys = [k for k in impl.config_keys if not config.get(k) and not os.getenv(k)]
        
        # 如果有缺失的key，但系统能自动获取（环境变量等），可以尝试执行
        if impl.executor:
            try:
                result = await self._execute_implementation(impl, config, {})
                return RouteResult(
                    success=True,
                    feature_id=feature_id,
                    implementation=impl.id,
                    implementation_name=impl.name,
                    level=impl.level.value,
                    message=f"自动配置成功，使用 {impl.name}",
                    data=result,
                )
            except Exception as e:
                logger.debug("Auto-config execution failed: %s", str(e))
        
        # 需要引导
        guide_flow = await self._create_guide_flow(feature_id, user_context)
        self._stats["guide_started"] += 1
        
        return RouteResult(
            success=False,
            feature_id=feature_id,
            implementation=impl.id,
            implementation_name=impl.name,
            level=impl.level.value,
            requires_guide=True,
            guide_flow=guide_flow,
            config_keys_needed=missing_keys,
            message=f"需要配置 {', '.join(missing_keys)}",
        )
    
    async def _try_fallback(
        self, 
        feature_id: str, 
        config: Dict[str, Any],
        input_data: Dict[str, Any],
        strategy: RouteStrategy
    ) -> RouteResult:
        """尝试降级方案"""
        fallback_chain = self._matrix.get_fallback_chain(feature_id, config)
        
        for impl in fallback_chain:
            if impl.id == self._matrix.get_best_available(feature_id, config, True):
                continue  # 跳过刚才失败的
            
            try:
                result = await self._execute_implementation(impl, config, input_data)
                self._stats["fallback_routes"] += 1
                
                return RouteResult(
                    success=True,
                    feature_id=feature_id,
                    implementation=impl.id,
                    implementation_name=impl.name,
                    level=impl.level.value,
                    message=f"降级使用 {impl.name}",
                    data=result,
                    accuracy=impl.accuracy,
                )
            except Exception as e:
                logger.debug("Fallback %s failed: %s", impl.id, str(e))
                continue
        
        return RouteResult(success=False, feature_id=feature_id)
    
    async def _execute_implementation(
        self, 
        impl: Implementation, 
        config: Dict[str, Any], 
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行实现"""
        # 如果有注册的执行器，使用执行器
        if impl.id in self._executors:
            executor = self._executors[impl.id]
            if callable(executor):
                if hasattr(executor, '__await__'):
                    return await executor(config, input_data)
                else:
                    return executor(config, input_data)
        
        # 如果实现有内置执行器
        if impl.executor:
            if hasattr(impl.executor, '__await__'):
                return await impl.executor(config, input_data)
            else:
                return impl.executor(config, input_data)
        
        # 返回元数据（未实际执行）
        return {
            "executed": False,
            "message": f"Implementation {impl.id} has no executor",
            "config_needed": impl.config_keys,
        }
    
    async def _start_guide(
        self, 
        feature_id: str, 
        user_context: Dict[str, Any]
    ) -> RouteResult:
        """启动引导"""
        guide_flow = await self._create_guide_flow(feature_id, user_context)
        self._stats["guide_started"] += 1
        
        return RouteResult(
            success=False,
            feature_id=feature_id,
            requires_guide=True,
            guide_flow=guide_flow,
            message=f"已为功能 {feature_id} 启动配置引导",
        )
    
    async def _create_guide_flow(
        self, 
        feature_id: str, 
        user_context: Dict[str, Any]
    ) -> Optional[GuideFlow]:
        """创建引导流程"""
        # 获取用户画像
        profile = self._profile_detector.detect_profile()
        
        # 合并上下文
        full_context = {
            **profile.to_dict(),
            **user_context,
        }
        
        # 根据用户画像选择引导类型
        preferred_type = None
        if profile.preferred_guide_types:
            preferred_type = profile.preferred_guide_types[0].value
        
        return self._guide.create_guide_flow(
            feature_id, 
            full_context,
            preferred_type
        )
    
    def _calc_latency(self, start_time: datetime) -> int:
        """计算延迟"""
        delta = datetime.now() - start_time
        return int(delta.total_seconds() * 1000)
    
    async def execute_feature_sync(
        self, 
        feature_id: str, 
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        strategy: RouteStrategy = RouteStrategy.BALANCED
    ) -> RouteResult:
        """
        同步执行功能（兼容同步调用）
        
        内部使用 asyncio 但不等待完成
        """
        import asyncio

        return await self.execute_feature(feature_id, input_data, config, strategy)
    
    def get_available_features(self) -> List[str]:
        """获取所有可用功能"""
        return self._matrix.get_all_features()
    
    def get_feature_status(
        self, 
        feature_id: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        获取功能状态
        
        返回功能的所有实现及其可用性
        """
        config = config or self._get_current_config()
        implementations = self._matrix.get_implementations(feature_id)
        
        status_list = []
        for impl in implementations:
            is_available = impl.is_available(config)
            status_list.append({
                "id": impl.id,
                "name": impl.name,
                "level": impl.level.value,
                "available": is_available,
                "accuracy": impl.accuracy,
                "latency_ms": impl.latency_ms,
                "requires_auth": impl.requires_auth,
                "config_keys": impl.config_keys,
            })
        
        return {
            "feature_id": feature_id,
            "implementations": status_list,
            "best_available": self._matrix.get_best_available(feature_id, config, True).id if self._matrix.get_best_available(feature_id, config, True) else None,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        return {
            **self._stats,
            "fallback_rate": (
                self._stats["fallback_routes"] / self._stats["total_requests"]
                if self._stats["total_requests"] > 0 else 0
            ),
        }
    
    def register_feature(
        self, 
        feature_id: str, 
        implementations: List[Implementation]
    ):
        """
        注册新功能及其实现
        
        Args:
            feature_id: 功能标识符
            implementations: 实现列表
        """
        self._matrix.register_feature(feature_id, implementations)
    
    def set_config(self, config: Dict[str, Any]):
        """
        设置配置
        
        用于运行时更新配置
        """
        # 更新环境变量
        for key, value in config.items():
            os.environ[key] = str(value)


# 全局实例
_router: Optional[AdaptiveRouter] = None


def get_adaptive_router() -> AdaptiveRouter:
    """获取自适应路由器全局实例"""
    global _router
    if _router is None:
        _router = AdaptiveRouter()
    return _router