"""
LivingTree NG - 模型管理器
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import time


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    available: bool = False
    description: str = ""
    backend: str = "ollama"


class ModelManager:
    """
    简化版模型管理器
    
    功能:
        - 获取可用模型列表
        - 切换当前模型
        - 管理模型配置
    """
    
    def __init__(self, config):
        self.config = config
        self.current_model = config.ollama.default_model
        self._cache_file = Path(config.paths.data) / "model_cache.json"
        self._model_cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """加载缓存"""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_cache(self):
        """保存缓存"""
        try:
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._model_cache, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def get_available_models(self) -> List[ModelInfo]:
        """
        获取可用模型列表
        
        包含:
            - 推荐模型（内置列表）
            - 本地已下载的模型
        """
        models = []
        
        # 推荐模型列表
        recommended = [
            ModelInfo(
                name="qwen2.5:0.5b",
                available=True,
                description="轻量级模型，快速响应",
                backend="ollama"
            ),
            ModelInfo(
                name="qwen2.5:1.5b",
                available=True,
                description="小型模型，平衡性能",
                backend="ollama"
            ),
            ModelInfo(
                name="qwen2.5:3b",
                available=True,
                description="中型模型，适合大多数任务",
                backend="ollama"
            ),
            ModelInfo(
                name="llama3.2:1b",
                available=True,
                description="Meta Llama 3.2 1B",
                backend="ollama"
            ),
            ModelInfo(
                name="llama3.2:3b",
                available=True,
                description="Meta Llama 3.2 3B",
                backend="ollama"
            )
        ]
        models.extend(recommended)
        
        return models
    
    def set_current_model(self, model_name: str) -> bool:
        """设置当前模型"""
        self.current_model = model_name
        self._model_cache["current_model"] = model_name
        self._save_cache()
        return True
    
    def get_current_model(self) -> str:
        """获取当前模型"""
        if "current_model" in self._model_cache:
            return self._model_cache["current_model"]
        return self.current_model
    
    def is_model_available(self, model_name: str) -> bool:
        """检查模型是否可用（简化版，始终返回True）"""
        return True
    
    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        models = self.get_available_models()
        for model in models:
            if model.name == model_name:
                return model
        return None


# 全局模型管理器实例（延迟初始化）
_model_manager_instance = None


def get_model_manager(config=None) -> ModelManager:
    """获取模型管理器实例"""
    global _model_manager_instance
    if _model_manager_instance is None and config is not None:
        _model_manager_instance = ModelManager(config)
    return _model_manager_instance
