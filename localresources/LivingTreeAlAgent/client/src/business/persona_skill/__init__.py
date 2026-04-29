# -*- coding: utf-8 -*-
"""
Persona Skill 系统 - 角色智库
=========================

将通用 AI 变成"销售总监/风控专家/谈判高手"的灵魂模版系统。

核心组件：
- models.py: 数据模型
- persona_loader.py: 角色加载器（内置 + GitHub）
- registry.py: 角色注册表
- persona_engine.py: 人格化引擎（集成 RelayFreeLLM + 记忆宫殿）

使用示例：
>>> from core.persona_skill import PersonaEngine, PersonaRegistry
>>> 
>>> # 创建引擎
>>> engine = PersonaEngine()
>>> 
>>> # 快捷咨询
>>> response = await engine.consult(
...     "有个客户价格卡在9折，怎么破？",
...     persona_type="colleague_sales"
... )
>>> print(response)
"""

from .models import (
    PersonaSkill,
    PersonaSession,
    PersonaCategory,
    PersonaTier,
    PersonaVariable,
    PersonaTrigger,
    PersonaInvokeResult,
)

from .registry import PersonaRegistry

from .persona_engine import PersonaEngine

from .persona_loader import PersonaLoader, BUILTIN_PERSONAS


__all__ = [
    # 模型
    "PersonaSkill",
    "PersonaSession",
    "PersonaCategory",
    "PersonaTier",
    "PersonaVariable",
    "PersonaTrigger",
    "PersonaInvokeResult",
    # 核心
    "PersonaRegistry",
    "PersonaEngine",
    "PersonaLoader",
    "BUILTIN_PERSONAS",
]


# 快捷函数
_default_engine = None

def get_engine() -> PersonaEngine:
    """获取全局引擎实例"""
    global _default_engine
    if _default_engine is None:
        _default_engine = PersonaEngine()
    return _default_engine


async def consult(question: str, persona_id: str = "colleague_sales") -> str:
    """
    快捷咨询函数

    用法：
    >>> response = await consult("客户嫌价格高怎么办？", "colleague_sales")
    """
    engine = get_engine()
    result = await engine.invoke(task=question, persona_id=persona_id)
    return result.response


def switch_persona(persona_id: str) -> bool:
    """切换当前角色"""
    engine = get_engine()
    return engine.switch_persona(persona_id)
