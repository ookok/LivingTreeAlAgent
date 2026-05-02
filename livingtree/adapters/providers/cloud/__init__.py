# -*- coding: utf-8 -*-
"""
Cloud Service Drivers - 云服务驱动器子包

调用云端 AI 厂商 API。
本质复用 OpenAI 兼容协议，仅通过配置区分。
"""

from .openai_compatible_driver import OpenAICompatibleDriver

__all__ = ["OpenAICompatibleDriver"]
