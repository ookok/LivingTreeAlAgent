# -*- coding: utf-8 -*-
"""
Local Service Drivers - 本地服务驱动器子包

连接本地运行的 OpenAI 兼容 API 服务。

支持：
  - Ollama /v1 端点
  - LM Studio
  - vLLM Server
  - LMDeploy
  - Text Generation WebUI
  - 任何 OpenAI 兼容 API
"""

from .openai_compatible_driver import OpenAICompatibleDriver

__all__ = ["OpenAICompatibleDriver"]
