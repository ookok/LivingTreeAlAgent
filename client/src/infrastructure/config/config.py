"""
配置管理模块 - 统一到 NanochatConfig
======================================

设计原则:
    1. 使用 NanochatConfig 作为后端配置（属性访问）
    2. AppConfig 仅用于基础设施层配置（窗口、主题等）
    3. 所有配置访问统一为属性风格
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# 导入 NanochatConfig
from .business.nanochat_config import (
    NanochatConfig,
    config as nanochat_config,
    EndpointConfig,
)


@dataclass
class AppConfig:
    """
    应用配置（基础设施层）
    
    注意: 后端配置（Ollama、API Keys 等）请使用 NanochatConfig:
        from .business.nanochat_config import config
        url = config.ollama.url
    
    此 AppConfig 仅用于 UI/窗口/主题等基础设施配置。
    """
    window_width: int = 1200
    window_height: int = 800
    left_panel_width: int = 250
    right_panel_width: int = 300
    theme: str = "light"  # light or dark
    language: str = "zh"
    
    # 后端配置（现在使用 NanochatConfig，此处仅作快捷访问）
    @property
    def ollama(self) -> EndpointConfig:
        """获取 Ollama 配置（从 NanochatConfig）"""
        return nanochat_config.ollama
    
    @property
    def api_keys(self) -> Dict[str, str]:
        """获取 API Keys（从 NanochatConfig，返回字典格式）"""
        keys = nanochat_config.api_keys
        result = {}
        for field_name in ['openai', 'anthropic', 'deepseek', 'moonshot', 'dashscope', 'modelscope', 'huggingface']:
            val = getattr(keys, field_name, None)
            if val:
                result[field_name] = val
        return result
    
    def __post_init__(self):
        """向后兼容：支持 dict 式访问"""
        pass  # 不再需要初始化 dict


# 默认配置
DEFAULT_CONFIG = AppConfig()


def get_config_dir() -> Path:
    """
    获取配置目录
    
    Returns:
        Path: 配置目录路径
    """
    config_dir = Path.home() / ".living.tree" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_models_dir() -> Path:
    """
    获取模型目录
    
    Returns:
        Path: 模型目录路径
    """
    models_dir = Path.home() / ".living.tree" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_projects_dir() -> Path:
    """
    获取项目目录
    
    Returns:
        Path: 项目目录路径
    """
    projects_dir = Path.home() / ".living.tree" / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    return projects_dir


def load_config() -> AppConfig:
    """
    加载配置
    
    Returns:
        AppConfig: 应用配置
    """
    config_path = get_config_dir() / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return AppConfig(**data)
        except Exception:
            pass
    return DEFAULT_CONFIG


def save_config(config: AppConfig):
    """
    保存配置
    
    Args:
        config: 应用配置
    """
    config_path = get_config_dir() / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "window_width": config.window_width,
                "window_height": config.window_height,
                "left_panel_width": config.left_panel_width,
                "right_panel_width": config.right_panel_width,
                "theme": config.theme,
                "language": config.language,
            },
            f,
            ensure_ascii=False,
            indent=2
        )


# 向后兼容：导出 NanochatConfig 的快捷访问
def get_ollama_config() -> EndpointConfig:
    """获取 Ollama 配置（快捷函数）"""
    return nanochat_config.ollama


def get_api_key(provider: str) -> Optional[str]:
    """获取 API Key（快捷函数）"""
    return getattr(nanochat_config.api_keys, provider, None)


# 导出
__all__ = [
    'AppConfig', 'DEFAULT_CONFIG',
    'load_config', 'save_config',
    'get_config_dir', 'get_models_dir', 'get_projects_dir',
    # 快捷访问
    'get_ollama_config', 'get_api_key',
    # NanochatConfig（推荐）
    'NanochatConfig', 'nanochat_config',
]
