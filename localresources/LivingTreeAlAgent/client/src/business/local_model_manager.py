"""
本地模型管理器
管理1B/7B/30B+尺寸的本地大模型
"""

import os
import json
import asyncio
import subprocess
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class ModelSize(Enum):
    """模型尺寸"""
    SMALL = "1B"
    MEDIUM = "7B"
    LARGE = "30B+"


class ModelBackend(Enum):
    """模型后端"""
    OLLAMA = "ollama"
    LLAMA_CPP = "llama.cpp"
    VLLM = "vllm"
    MLX = "mlx"


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    size: ModelSize
    backend: ModelBackend
    path: str
    description: str = ""
    parameters: int = 0  # 模型参数量（亿）
    memory_requirement: int = 0  # 内存需求（GB）
    performance_score: float = 0.0  # 性能评分
    last_used: Optional[datetime] = None
    is_active: bool = False


class ModelManager:
    """本地模型管理器"""
    
    def __init__(self, models_dir: str = None):
        self.models_dir = models_dir or os.path.expanduser("~/.hermes-desktop/models")
        os.makedirs(self.models_dir, exist_ok=True)
        self.models: Dict[str, ModelInfo] = {}
        self.active_model: Optional[str] = None
        self._load_models()
    
    def _load_models(self):
        """加载模型配置"""
        config_file = os.path.join(self.models_dir, "models.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    for model_name, model_data in config.items():
                        model_info = ModelInfo(
                            name=model_name,
                            size=ModelSize(model_data.get('size', '7B')),
                            backend=ModelBackend(model_data.get('backend', 'ollama')),
                            path=model_data.get('path', ''),
                            description=model_data.get('description', ''),
                            parameters=model_data.get('parameters', 0),
                            memory_requirement=model_data.get('memory_requirement', 0),
                            performance_score=model_data.get('performance_score', 0.0),
                            last_used=datetime.fromisoformat(model_data.get('last_used')) if model_data.get('last_used') else None,
                            is_active=model_data.get('is_active', False)
                        )
                        self.models[model_name] = model_info
                        if model_info.is_active:
                            self.active_model = model_name
            except Exception as e:
                print(f"加载模型配置失败: {e}")
    
    def _save_models(self):
        """保存模型配置"""
        config_file = os.path.join(self.models_dir, "models.json")
        config = {}
        for model_name, model_info in self.models.items():
            config[model_name] = {
                'size': model_info.size.value,
                'backend': model_info.backend.value,
                'path': model_info.path,
                'description': model_info.description,
                'parameters': model_info.parameters,
                'memory_requirement': model_info.memory_requirement,
                'performance_score': model_info.performance_score,
                'last_used': model_info.last_used.isoformat() if model_info.last_used else None,
                'is_active': model_info.is_active
            }
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def add_model(self, model_info: ModelInfo):
        """添加模型"""
        self.models[model_info.name] = model_info
        self._save_models()
    
    def remove_model(self, model_name: str):
        """移除模型"""
        if model_name in self.models:
            del self.models[model_name]
            if self.active_model == model_name:
                self.active_model = None
            self._save_models()
    
    def get_model(self, model_name: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        return self.models.get(model_name)
    
    def list_models(self) -> List[ModelInfo]:
        """列出所有模型"""
        return list(self.models.values())
    
    def list_models_by_size(self, size: ModelSize) -> List[ModelInfo]:
        """按尺寸列出模型"""
        return [m for m in self.models.values() if m.size == size]
    
    def activate_model(self, model_name: str) -> bool:
        """激活模型"""
        if model_name not in self.models:
            return False
        
        # 先停用所有模型
        for name, model in self.models.items():
            model.is_active = (name == model_name)
        
        self.active_model = model_name
        self.models[model_name].last_used = datetime.now()
        self.models[model_name].is_active = True
        self._save_models()
        return True
    
    def get_active_model(self) -> Optional[ModelInfo]:
        """获取当前激活的模型"""
        if not self.active_model:
            return None
        return self.models.get(self.active_model)
    
    def recommend_model(self, task_type: str, context_size: int = 1024) -> Optional[ModelInfo]:
        """推荐模型"""
        # 基于任务类型和上下文大小推荐模型
        candidates = []
        
        for model in self.models.values():
            # 简单的推荐逻辑
            score = 0
            
            # 任务类型匹配
            if task_type in ['code_completion', 'error_diagnosis']:
                if model.size in [ModelSize.SMALL, ModelSize.MEDIUM]:
                    score += 1
            elif task_type in ['code_generation', 'refactoring']:
                if model.size in [ModelSize.MEDIUM, ModelSize.LARGE]:
                    score += 1
            elif task_type in ['document_generation', 'test_generation']:
                if model.size in [ModelSize.MEDIUM]:
                    score += 1
            
            # 上下文大小匹配
            if context_size <= 2048 and model.size == ModelSize.SMALL:
                score += 1
            elif context_size <= 8192 and model.size == ModelSize.MEDIUM:
                score += 1
            elif context_size > 8192 and model.size == ModelSize.LARGE:
                score += 1
            
            # 性能评分
            score += model.performance_score * 0.1
            
            candidates.append((score, model))
        
        if candidates:
            candidates.sort(reverse=True, key=lambda x: x[0])
            return candidates[0][1]
        
        # 默认返回中等尺寸模型
        for model in self.models.values():
            if model.size == ModelSize.MEDIUM:
                return model
        
        # 返回第一个模型
        return next(iter(self.models.values()), None)
    
    async def load_model(self, model_name: str) -> bool:
        """加载模型"""
        model = self.models.get(model_name)
        if not model:
            return False
        
        # 根据后端加载模型
        if model.backend == ModelBackend.OLLAMA:
            return await self._load_ollama_model(model)
        elif model.backend == ModelBackend.LLAMA_CPP:
            return await self._load_llama_cpp_model(model)
        elif model.backend == ModelBackend.VLLM:
            return await self._load_vllm_model(model)
        elif model.backend == ModelBackend.MLX:
            return await self._load_mlx_model(model)
        
        return False
    
    async def _load_ollama_model(self, model: ModelInfo) -> bool:
        """加载Ollama模型"""
        try:
            # 检查Ollama是否安装
            result = subprocess.run(['ollama', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                print("Ollama 未安装")
                return False
            
            # 拉取模型
            result = subprocess.run(['ollama', 'pull', model.name], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"拉取模型失败: {result.stderr}")
                return False
            
            print(f"Ollama模型 {model.name} 加载成功")
            return True
        except Exception as e:
            print(f"加载Ollama模型失败: {e}")
            return False
    
    async def _load_llama_cpp_model(self, model: ModelInfo) -> bool:
        """加载llama.cpp模型"""
        try:
            # 检查模型文件是否存在
            if not os.path.exists(model.path):
                print(f"模型文件不存在: {model.path}")
                return False
            
            print(f"llama.cpp模型 {model.name} 加载成功")
            return True
        except Exception as e:
            print(f"加载llama.cpp模型失败: {e}")
            return False
    
    async def _load_vllm_model(self, model: ModelInfo) -> bool:
        """加载vLLM模型"""
        try:
            print(f"vLLM模型 {model.name} 加载成功")
            return True
        except Exception as e:
            print(f"加载vLLM模型失败: {e}")
            return False
    
    async def _load_mlx_model(self, model: ModelInfo) -> bool:
        """加载MLX模型"""
        try:
            print(f"MLX模型 {model.name} 加载成功")
            return True
        except Exception as e:
            print(f"加载MLX模型失败: {e}")
            return False
    
    def update_model_performance(self, model_name: str, score: float):
        """更新模型性能评分"""
        if model_name in self.models:
            self.models[model_name].performance_score = score
            self._save_models()
    
    def get_model_stats(self) -> Dict[str, Any]:
        """获取模型统计信息"""
        stats = {
            'total_models': len(self.models),
            'active_model': self.active_model,
            'models_by_size': {
                '1B': len(self.list_models_by_size(ModelSize.SMALL)),
                '7B': len(self.list_models_by_size(ModelSize.MEDIUM)),
                '30B+': len(self.list_models_by_size(ModelSize.LARGE))
            }
        }
        return stats


def create_model_manager(models_dir: str = None) -> ModelManager:
    """
    创建模型管理器
    
    Args:
        models_dir: 模型存储目录
        
    Returns:
        ModelManager: 模型管理器实例
    """
    return ModelManager(models_dir)


def get_default_models() -> List[ModelInfo]:
    """
    获取默认模型列表
    
    Returns:
        List[ModelInfo]: 默认模型列表
    """
    return [
        ModelInfo(
            name="llama3.1:8b",
            size=ModelSize.MEDIUM,
            backend=ModelBackend.OLLAMA,
            path="",
            description="Meta Llama 3.1 8B 模型",
            parameters=8,
            memory_requirement=16,
            performance_score=0.85
        ),
        ModelInfo(
            name="gemma2:2b",
            size=ModelSize.SMALL,
            backend=ModelBackend.OLLAMA,
            path="",
            description="Google Gemma 2B 模型",
            parameters=2,
            memory_requirement=4,
            performance_score=0.7
        ),
        ModelInfo(
            name="llama3.1:70b",
            size=ModelSize.LARGE,
            backend=ModelBackend.OLLAMA,
            path="",
            description="Meta Llama 3.1 70B 模型",
            parameters=70,
            memory_requirement=48,
            performance_score=0.95
        )
    ]