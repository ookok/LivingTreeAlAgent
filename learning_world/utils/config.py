"""
配置工具
"""

import os
from pathlib import Path
from typing import Optional


def get_learning_world_dir() -> Path:
    """获取学习世界数据目录"""
    user_dir = Path.home() / ".hermes-desktop" / "learning_world"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def get_profile_db_path() -> Path:
    """获取用户画像数据库路径"""
    return get_learning_world_dir() / "profiles.db"


def get_sessions_dir() -> Path:
    """获取会话存储目录"""
    sessions_dir = get_learning_world_dir() / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir


def get_resources_dir() -> Path:
    """获取资源目录"""
    return Path(__file__).parent.parent / "ui" / "resources"


# 默认配置
DEFAULT_CONFIG = {
    "max_tags": 8,
    "max_suggestions": 3,
    "difficulty": "normal",  # easy, normal, advanced
    "show_reasoning": False,
    "auto_save": True,
    "theme": "dark",
}


def load_config() -> dict:
    """加载配置"""
    config_path = get_learning_world_dir() / "config.json"
    
    if config_path.exists():
        import json
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """保存配置"""
    config_path = get_learning_world_dir() / "config.json"
    
    import json
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
