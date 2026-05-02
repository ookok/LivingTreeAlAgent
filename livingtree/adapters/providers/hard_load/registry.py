# -*- coding: utf-8 -*-
"""
Hard Driver Registry - 硬加载驱动器注册表

管理所有硬加载后端的注册和工厂创建。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type

from ..base import DriverMode, ModelDriver

logger = logging.getLogger(__name__)

# 后端注册表: backend_name -> {class, default_params}
_HARD_BACKEND_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_hard_backend(
    backend: str,
    driver_class: Type[ModelDriver],
    default_params: Dict[str, Any] | None = None,
) -> None:
    """注册硬加载后端"""
    _HARD_BACKEND_REGISTRY[backend] = {
        "class": driver_class,
        "params": default_params or {},
    }
    logger.debug(f"注册硬加载后端: {backend} -> {driver_class.__name__}")


def get_hard_backend(backend: str) -> Optional[Dict[str, Any]]:
    """获取硬加载后端信息"""
    return _HARD_BACKEND_REGISTRY.get(backend)


def list_backends() -> list:
    """列出所有已注册的后端"""
    return list(_HARD_BACKEND_REGISTRY.keys())


def create_hard_driver(
    backend: str,
    name: str = "",
    **kwargs,
) -> ModelDriver:
    """
    工厂方法：创建硬加载驱动器实例

    Args:
        backend: 后端名称 (llama_cpp/ollama/vllm/unsloth)
        name: 驱动器名称
        **kwargs: 传递给驱动器构造函数的参数
    """
    info = get_hard_backend(backend)
    if not info:
        raise ValueError(
            f"未知硬加载后端: {backend}，"
            f"可用: {list_backends()}"
        )
    driver_class = info["class"]
    default_params = info["params"]
    # 合并默认参数
    merged = {**default_params, **kwargs}
    merged.setdefault("name", name or f"hardload-{backend}")
    return driver_class(**merged)
