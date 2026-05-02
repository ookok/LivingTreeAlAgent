# -*- coding: utf-8 -*-
"""
Hard Load Drivers - 硬加载驱动器子包

直接本地加载模型文件进行推理，不依赖外部服务。

已内置后端：
  - llama_cpp: llama-cpp-python 加载 GGUF
  - ollama: Ollama 本地 API 管理
  - vllm: vLLM 推理引擎
  - unsloth: Unsloth 高效推理
"""

from .registry import (
    register_hard_backend,
    get_hard_backend,
    list_backends,
    create_hard_driver,
)

__all__ = [
    "register_hard_backend",
    "get_hard_backend",
    "list_backends",
    "create_hard_driver",
]
