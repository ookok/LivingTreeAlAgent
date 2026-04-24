# -*- coding: utf-8 -*-
"""
统一配置获取器 - Unified Config Provider
==========================================

提供全局配置获取，确保 Ollama 等服务地址统一从配置读取。

使用示例：
```python
from core.config_provider import get_ollama_url, get_ollama_config, get_default_model

url = get_ollama_url()  # http://www.mogoo.com.cn:8899/v1
config = get_ollama_config()
model = get_default_model("l0")
```
"""

from __future__ import annotations

import os
from typing import Optional

# 默认配置（当配置文件不存在时使用）
DEFAULT_OLLAMA_URL = "http://www.mogoo.com.cn:8899/v1"
DEFAULT_MODELS = {
    "l0": "qwen2.5:0.5b",      # 快速路由/意图分类
    "l1": "qwen2.5:1.5b",      # 轻量推理/搜索
    "l3": "qwen3.5:4b",        # 推理/意图理解
    "l4": "qwen3.5:9b",        # 深度生成/思考模式
    "embedding": "nomic-embed-text",
}

# 全局缓存
_cached_config: Optional[dict] = None


def _load_config() -> dict:
    """从配置文件加载配置（延迟加载，避免循环依赖）"""
    global _cached_config

    if _cached_config is not None:
        return _cached_config

    config_data = {
        "ollama_url": DEFAULT_OLLAMA_URL,
        "models": DEFAULT_MODELS.copy(),
    }

    # 尝试从环境变量读取
    env_url = os.environ.get("OLLAMA_BASE_URL")
    if env_url:
        config_data["ollama_url"] = env_url

    # 尝试从配置文件读取
    config_path = os.path.join(os.path.dirname(__file__), "config_data.json")
    if os.path.exists(config_path):
        try:
            import json
from core.logger import get_logger
logger = get_logger('config_provider')

            with open(config_path, encoding="utf-8") as f:
                file_config = json.load(f)
                if "ollama_url" in file_config:
                    config_data["ollama_url"] = file_config["ollama_url"]
                if "models" in file_config:
                    config_data["models"].update(file_config["models"])
        except Exception:
            pass

    _cached_config = config_data
    return config_data


def get_ollama_url() -> str:
    """获取 Ollama 服务地址"""
    return _load_config()["ollama_url"]


def get_ollama_config() -> dict:
    """获取完整 Ollama 配置"""
    return _load_config()


def get_default_model(level: str = "l0") -> str:
    """
    获取指定层级的默认模型

    Args:
        level: 模型层级 (l0/l1/l3/l4/embedding)

    Returns:
        str: 模型名称
    """
    models = _load_config()["models"]
    return models.get(level, DEFAULT_MODELS.get(level, "qwen2.5:1.5b"))


def get_model_for_intent(intent: str) -> str:
    """
    根据意图类型获取合适的模型

    Args:
        intent: 意图类型 (factual/conversational/procedural/creative/task/writing)

    Returns:
        str: 模型名称
    """
    intent_model_map = {
        "factual": "l1",         # 事实查询 → L1 轻量
        "conversational": "l1",  # 对话类 → L1 轻量
        "procedural": "l3",      # 流程/代码 → L3 推理
        "creative": "l4",        # 创意类 → L4 深度
        "task": "l3",            # 任务执行 → L3 推理
        "writing": "l3",          # 写作类 → L3 推理
        "unknown": "l1",         # 未知 → L1 轻量
    }
    level = intent_model_map.get(intent.lower(), "l1")
    return get_default_model(level)


def reload_config():
    """重新加载配置（清除缓存）"""
    global _cached_config
    _cached_config = None


# ── 便捷导出 ──────────────────────────────────────────────────────────────


def get_l0_model() -> str:
    """获取 L0 模型（快速路由/意图分类）"""
    return get_default_model("l0")


def get_l1_model() -> str:
    """获取 L1 模型（轻量推理）"""
    return get_default_model("l1")


def get_l3_model() -> str:
    """获取 L3 模型（推理/意图理解）"""
    return get_default_model("l3")


def get_l4_model() -> str:
    """获取 L4 模型（深度生成）"""
    return get_default_model("l4")


def get_embedding_model() -> str:
    """获取 Embedding 模型"""
    return get_default_model("embedding")


if __name__ == "__main__":
    # 测试
    logger.info(f"Ollama URL: {get_ollama_url()}")
    logger.info(f"L0 Model: {get_l0_model()}")
    logger.info(f"L1 Model: {get_l1_model()}")
    logger.info(f"L3 Model: {get_l3_model()}")
    logger.info(f"L4 Model: {get_l4_model()}")
    logger.info(f"Embedding Model: {get_embedding_model()}")
