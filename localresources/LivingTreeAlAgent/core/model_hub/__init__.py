# -*- coding: utf-8 -*-
"""
=============================================
Model Hub - 统一模型下载管理器
=============================================

将阿里魔塔社区 (ModelScope)、HuggingFace Hub、GitHub 等模型源
封装为统一的下载接口，支持：
- 模型名模糊匹配
- 多源搜索与自动降级
- 本地加载兼容 ollama / llama_cpp / vllm / unsloth

Author: Hermes Desktop AI Assistant
"""

from .manager import ModelHubManager, HubConfig
from .resolver import ModelResolver, ModelMatchResult, ModelSource
from .sources import ModelScopeSource, HuggingFaceSource, GithubSource, DownloadConfig, DownloadProgress
from .loader import ModelLoader, LoadConfig, LoadResult, LoadBackend, LoaderBase
from .registry import ModelRegistry, ModelRecord

__all__ = [
    "ModelHubManager",
    "HubConfig",
    "ModelResolver",
    "ModelMatchResult",
    "ModelSource",
    "ModelScopeSource",
    "HuggingFaceSource",
    "GithubSource",
    "DownloadConfig",
    "DownloadProgress",
    "ModelLoader",
    "LoadConfig",
    "LoadResult",
    "LoadBackend",
    "LoaderBase",
    "ModelRegistry",
    "ModelRecord",
]
