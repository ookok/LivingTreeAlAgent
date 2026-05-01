# -*- coding: utf-8 -*-
"""
统一下载系统
Unified Download System

导出核心组件和快捷函数

注意：本系统已不再支持本地模型文件下载（GGUF/BIN/Safetensors格式），
所有模型调用均通过远程 URL 进行。推荐使用 FlowyAIPC Herdsman 引擎。
"""

from .download_center import (
    DownloadCenter,
    DownloadTask,
    DownloadStatus,
    SourceType,
    get_download_center,
    download_file,
)

__all__ = [
    "DownloadCenter",
    "DownloadTask",
    "DownloadStatus",
    "SourceType",
    "get_download_center",
    "download_file",
]