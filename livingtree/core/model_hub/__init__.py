"""
Model Hub - 统一模型下载管理器

将 ModelScope、HuggingFace Hub、GitHub 等模型源封装为统一接口
"""

from .manager import ModelHubManager, HubConfig
from .resolver import ModelResolver, ModelMatchResult, ModelSource
from .sources import ModelScopeSource, HuggingFaceSource, GithubSource, DownloadConfig, DownloadProgress
from .loader import ModelLoader, LoadConfig, LoadResult, LoadBackend, LoaderBase
from .registry import ModelRegistry, ModelRecord

__all__ = [
    "ModelHubManager", "HubConfig",
    "ModelResolver", "ModelMatchResult", "ModelSource",
    "ModelScopeSource", "HuggingFaceSource", "GithubSource", "DownloadConfig", "DownloadProgress",
    "ModelLoader", "LoadConfig", "LoadResult", "LoadBackend", "LoaderBase",
    "ModelRegistry", "ModelRecord",
]
