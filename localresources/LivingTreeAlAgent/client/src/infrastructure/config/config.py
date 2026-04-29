"""
配置管理模块
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    """应用配置"""
    window_width: int = 1200
    window_height: int = 800
    left_panel_width: int = 250
    right_panel_width: int = 300
    theme: str = "light"  # light or dark
    language: str = "zh"
    ollama: Dict[str, Any] = None
    api_keys: Dict[str, str] = None
    
    def __post_init__(self):
        if self.ollama is None:
            self.ollama = {
                "base_url": "http://localhost:11434",
                "default_model": "qwen2.5:0.5b",
                "timeout": 30
            }
        if self.api_keys is None:
            self.api_keys = {}


DEFAULT_CONFIG = AppConfig()


def get_config_dir() -> Path:
    """
    获取配置目录
    
    Returns:
        Path: 配置目录路径
    """
    config_dir = Path.home() / ".livingtree" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_models_dir() -> Path:
    """
    获取模型目录
    
    Returns:
        Path: 模型目录路径
    """
    models_dir = Path.home() / ".livingtree" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_projects_dir() -> Path:
    """
    获取项目目录
    
    Returns:
        Path: 项目目录路径
    """
    projects_dir = Path.home() / ".livingtree" / "projects"
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
                "ollama": config.ollama,
                "api_keys": config.api_keys
            },
            f,
            ensure_ascii=False,
            indent=2
        )
