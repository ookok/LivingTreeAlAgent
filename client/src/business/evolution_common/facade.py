"""
Evolution Common - 门面类

为所有进化引擎提供统一调用接口（门面模式）。
不修改原有实现，只包装调用。
"""

from typing import List, Dict, Any, Optional
from client.src.business.evolution_common import (
    BaseEvolutionEngine,
    EvolutionTarget,
    EvolutionConfig,
    create_evolution_engine,
)
import logging

logger = logging.getLogger(__name__)


class EvolutionEngineFacade:
    """
    进化引擎门面
    
    为所有领域的进化引擎提供统一接口。
    内部根据 target 路由到具体实现。
    
    Usage:
        facade = EvolutionEngineFacade()
        
        # 技能进化
        engine = facade.get_engine(EvolutionTarget.SKILL, database=db)
        
        # 代码进化
        engine = facade.get_engine(
            EvolutionTarget.CODE, 
            project_root=".", 
            config={"max_iterations": 10}
        )
        
        # 统一调用（如果引擎实现了公共接口）
        result = engine.evolve(...)
    """
    
    def __init__(self):
        self._engines: Dict[str, Any] = {}
        logger.info("[EvolutionEngineFacade] 初始化完成")
    
    def get_engine(
        self,
        target: EvolutionTarget,
        config: Optional[EvolutionConfig] = None,
        **kwargs,
    ) -> Any:
        """
        获取指定类型的进化引擎（单例）
        
        Args:
            target: 进化目标类型
            config: 进化配置
            **kwargs: 传递给具体引擎构造函数的参数
            
        Returns:
            对应的进化引擎实例
        """
        key = f"{target.value}_{hash(str(kwargs))}"
        
        if key not in self._engines:
            engine = create_evolution_engine(target, config, **kwargs)
            self._engines[key] = engine
            logger.info(f"[EvolutionEngineFacade] 创建引擎: {target.value}")
        
        return self._engines[key]
    
    def list_engines(self) -> List[str]:
        """列出所有已创建的引擎"""
        return list(self._engines.keys())
    
    def clear(self):
        """清空所有引擎实例"""
        self._engines.clear()
        logger.info("[EvolutionEngineFacade] 已清空所有引擎")


# ============================================================
# 便捷函数
# ============================================================

_default_facade: Optional[EvolutionEngineFacade] = None


def get_evolution_facade() -> EvolutionEngineFacade:
    """获取默认门面实例（单例）"""
    global _default_facade
    if _default_facade is None:
        _default_facade = EvolutionEngineFacade()
    return _default_facade


def evolve_skill(database, **kwargs) -> Any:
    """
    便捷函数：执行技能进化
    
    Args:
        database: EvolutionDatabase 实例
        **kwargs: 传递给引擎的参数
        
    Returns:
        进化结果
    """
    facade = get_evolution_facade()
    engine = facade.get_engine(EvolutionTarget.SKILL, database=database)
    
    # 调用具体方法（不同引擎接口不同，这里需要适配）
    if hasattr(engine, 'consolidate'):
        # SkillEvolutionEngine
        return engine.consolidate(**kwargs)
    else:
        logger.warning("[evolve_skill] 引擎不支持 consolidate() 方法")
        return None


def evolve_knowledge(**kwargs) -> Any:
    """
    便捷函数：执行知识图谱进化
    
    Args:
        **kwargs: 传递给引擎的参数
        
    Returns:
        进化结果
    """
    facade = get_evolution_facade()
    engine = facade.get_engine(EvolutionTarget.KNOWLEDGE, **kwargs)
    
    if hasattr(engine, 'evolve'):
        return engine.evolve(**kwargs)
    else:
        logger.warning("[evolve_knowledge] 引擎不支持 evolve() 方法")
        return None


__all__ = [
    "EvolutionEngineFacade",
    "get_evolution_facade",
    "evolve_skill",
    "evolve_knowledge",
]
