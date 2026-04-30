"""统一集成启动器 - 一键启动所有模块"""

from typing import Dict, Any, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)

class UnifiedIntegrationBootstrapper:
    """统一集成启动器"""
    
    def __init__(self):
        self._modules: Dict[str, Any] = {}
        self._initialized = False
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """一键初始化所有模块"""
        if self._initialized:
            logger.warning("已初始化，跳过")
            return
        
        logger.info("[Bootstrapper] 开始初始化所有模块...")
        
        init_order = [
            ("event_bus", self._init_event_bus),
            ("memory", self._init_memory_layer),
            ("search", self._init_search_engine),
            ("skill", self._init_skill_system),
            ("verifier", self._init_verifier),
            ("message", self._init_message_sync),
            ("optimization", self._init_optimization),
            ("evolution", self._init_evolution),
        ]
        
        for name, init_func in init_order:
            try:
                logger.info(f"[Bootstrapper] 初始化 {name}...")
                result = await init_func(config)
                self._modules[name] = result
                logger.info(f"[Bootstrapper] {name} 初始化成功")
            except Exception as e:
                logger.error(f"[Bootstrapper] {name} 初始化失败: {e}")
        
        self._initialized = True
        logger.info("[Bootstrapper] 所有模块初始化完成")
    
    async def _init_event_bus(self, config):
        from .enhanced_event_bus import get_enhanced_event_bus
        return get_enhanced_event_bus()
    
    async def _init_memory_layer(self, config):
        from .unified_memory_layer import get_unified_memory_layer
        layer = get_unified_memory_layer()
        await layer.initialize()
        return layer
    
    async def _init_search_engine(self, config):
        from .unified_search_engine import get_unified_search_engine
        engine = get_unified_search_engine()
        await engine.initialize()
        return engine
    
    async def _init_skill_system(self, config):
        from .skill_integration_service import SkillIntegrationService
        service = SkillIntegrationService()
        await service.initialize()
        return service
    
    async def _init_verifier(self, config):
        from .verifier_integration_service import VerifierIntegrationService
        service = VerifierIntegrationService()
        await service.initialize()
        return service
    
    async def _init_message_sync(self, config):
        from .message_sync_service import MessageSyncService
        service = MessageSyncService()
        await service.initialize()
        return service
    
    async def _init_optimization(self, config):
        from .intelligent_optimization_engine import IntelligentOptimizationEngine
        engine = IntelligentOptimizationEngine()
        await engine.initialize()
        return engine
    
    async def _init_evolution(self, config):
        from .self_evolution_engine import SelfEvolutionEngine
        engine = SelfEvolutionEngine()
        await engine.initialize()
        return engine
    
    def get_module(self, name: str):
        """获取模块实例"""
        return self._modules.get(name)
    
    @property
    def is_initialized(self):
        """是否已初始化"""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "initialized": self._initialized,
            "modules": list(self._modules.keys()),
            "module_count": len(self._modules),
        }

_bootstrapper_instance = None

def get_bootstrapper() -> UnifiedIntegrationBootstrapper:
    """获取集成启动器实例"""
    global _bootstrapper_instance
    if _bootstrapper_instance is None:
        _bootstrapper_instance = UnifiedIntegrationBootstrapper()
    return _bootstrapper_instance

async def initialize_all(config: Optional[Dict[str, Any]] = None):
    """一键初始化所有模块"""
    bootstrapper = get_bootstrapper()
    await bootstrapper.initialize(config)
    return bootstrapper