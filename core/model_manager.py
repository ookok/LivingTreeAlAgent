#!/usr/bin/env python3
"""
模型管理器
负责模型的检测、选择、下载和管理
"""

import os
import json
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from core.config import AppConfig, OllamaConfig
from core.ollama_client import OllamaClient
from core.model_priority_loader import ModelBackend, LocalModelPriorityLoader


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    path: Optional[str] = None
    size: Optional[int] = None
    backend: Optional[ModelBackend] = None
    available: bool = False
    description: str = ""


class ModelManager:
    """模型管理器"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.ollama_client = OllamaClient(config.ollama)
        self.priority_loader = LocalModelPriorityLoader()
        self._models_dir = Path(config.model_path.models_dir or "models")
        self._models_dir.mkdir(parents=True, exist_ok=True)
    
    def get_available_models(self) -> List[ModelInfo]:
        """获取所有可用模型"""
        models = []
        
        # 检查本地GGUF模型
        local_models = self._get_local_gguf_models()
        models.extend(local_models)
        
        # 检查Ollama模型
        ollama_models = self._get_ollama_models()
        models.extend(ollama_models)
        
        # 检查推荐模型
        recommended_models = self._get_recommended_models()
        for rec_model in recommended_models:
            # 检查是否已存在
            exists = any(m.name == rec_model.name for m in models)
            if not exists:
                models.append(rec_model)
        
        return models
    
    def _get_local_gguf_models(self) -> List[ModelInfo]:
        """获取本地GGUF模型"""
        models = []
        
        # 支持的GGUF文件扩展名
        gguf_exts = [".gguf", ".gguf.bin"]
        
        # 扫描models目录
        if self._models_dir.exists():
            for f in self._models_dir.rglob("*"):
                if f.suffix.lower() in gguf_exts:
                    model = ModelInfo(
                        name=f.stem,
                        path=str(f),
                        size=f.stat().st_size,
                        backend=ModelBackend.LLAMA_CPP,
                        available=True,
                        description=f"本地GGUF模型"
                    )
                    models.append(model)
        
        return models
    
    def get_available_local_models(self) -> List[ModelInfo]:
        """获取所有可用的本地模型"""
        return [model for model in self.get_available_models() if model.available and model.backend == ModelBackend.LLAMA_CPP]
    
    def use_local_model(self, model_name: str) -> bool:
        """使用本地模型
        
        Args:
            model_name: 模型名称
        
        Returns:
            bool: 是否成功
        """
        try:
            # 检查本地模型是否存在
            local_models = self._get_local_gguf_models()
            model_info = None
            for model in local_models:
                if model.name == model_name:
                    model_info = model
                    break
            
            if not model_info:
                print(f"[ModelManager] 本地模型不存在: {model_name}")
                return False
            
            # 加载模型
            client = self.load_model(model_info)
            if client:
                print(f"[ModelManager] 成功加载本地模型: {model_name}")
                return True
            else:
                print(f"[ModelManager] 加载本地模型失败: {model_name}")
                return False
        except Exception as e:
            print(f"[ModelManager] 使用本地模型时出错: {e}")
            return False
    
    def _get_ollama_models(self) -> List[ModelInfo]:
        """获取Ollama模型"""
        models = []
        
        try:
            ollama_models = self.ollama_client.list_models()
            for m in ollama_models:
                model = ModelInfo(
                    name=m.name,
                    size=m.size,
                    backend=ModelBackend.OLLAMA,
                    available=True,
                    description="Ollama模型"
                )
                models.append(model)
        except Exception:
            pass
        
        return models
    
    def _get_recommended_models(self) -> List[ModelInfo]:
        """获取推荐模型"""
        recommended = [
            {
                "name": "qwen2.5:0.5b",
                "description": "轻量级模型，适合快速响应",
                "size": 1.1e9  # 1.1GB
            },
            {
                "name": "qwen2.5:1.5b",
                "description": "小型模型，平衡性能和质量",
                "size": 3.1e9  # 3.1GB
            },
            {
                "name": "qwen2.5:3b",
                "description": "中型模型，适合大多数任务",
                "size": 6.1e9  # 6.1GB
            },
            {
                "name": "qwen2.5:7b",
                "description": "大型模型，提供高质量输出",
                "size": 14e9  # 14GB
            },
            {
                "name": "llama3.2:1b",
                "description": "Meta Llama 3.2 1B模型",
                "size": 2e9  # 2GB
            },
            {
                "name": "llama3.2:3b",
                "description": "Meta Llama 3.2 3B模型",
                "size": 6e9  # 6GB
            }
        ]
        
        models = []
        for rec in recommended:
            model = ModelInfo(
                name=rec["name"],
                size=rec["size"],
                backend=ModelBackend.OLLAMA,
                available=False,
                description=rec["description"]
            )
            models.append(model)
        
        return models
    
    def download_model(self, model_name: str, progress_callback=None) -> bool:
        """下载模型
        
        Args:
            model_name: 模型名称
            progress_callback: 进度回调函数，接收 (current, total, status) 参数
        
        Returns:
            bool: 是否下载成功
        """
        try:
            print(f"[ModelManager] 开始下载模型: {model_name}")
            
            # 检查本地是否已经有模型文件
            import os
            local_models = self._get_local_gguf_models()
            for model in local_models:
                if model.name == model_name:
                    print(f"[ModelManager] 模型已存在本地: {model_name}")
                    if progress_callback:
                        progress_callback(100, 100, "模型已存在")
                    return True
            
            # 使用统一下载中心下载ggUF文件
            from core.unified_downloader import get_download_center
            from core.unified_downloader import DownloadStatus, SourceType
            
            # 定义下载源列表，优先使用国内镜像
            download_sources = [
                {
                    "url": f"https://modelscope.cn/models/LLM-Research/Qwen2.5-0.5B-Instruct-GGUF/resolve/master/qwen2.5-0.5b-instruct-q4_k_m.gguf",
                    "source": SourceType.MODELSCOPE,
                    "source_info": "LLM-Research/Qwen2.5-0.5B-Instruct-GGUF",
                    "name": "ModelScope (国内镜像)"
                },
                {
                    "url": f"https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
                    "source": SourceType.HUGGINGFACE,
                    "source_info": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
                    "name": "HuggingFace"
                }
            ]
            
            save_dir = self._models_dir
            print(f"[ModelManager] 保存目录: {save_dir}")
            
            # 尝试从多个源下载
            for source_info in download_sources:
                model_url = source_info["url"]
                source_type = source_info["source"]
                source_name = source_info["name"]
                
                print(f"[ModelManager] 尝试从 {source_name} 下载: {model_url}")
                
                # 定义进度回调
                def on_progress(task):
                    print(f"[ModelManager] 进度回调: {task.status.value}, {task.progress:.1f}%")
                    if progress_callback:
                        status_map = {
                            "pending": "等待中...",
                            "downloading": "下载中...",
                            "paused": "已暂停",
                            "completed": "下载完成",
                            "failed": "下载失败",
                            "cancelled": "已取消"
                        }
                        status = status_map.get(task.status.value, "未知状态")
                        progress_callback(int(task.progress), 100, f"{status} - {task.speed_str} - {task.eta_str}")
                
                # 获取下载中心
                download_center = get_download_center()
                print(f"[ModelManager] 下载中心获取成功")
                
                # 创建下载任务
                print(f"[ModelManager] 创建下载任务...")
                task = download_center.create_task(
                    url=model_url,
                    save_path=save_dir,
                    source=source_type,
                    source_info=source_info["source_info"],
                    progress_callback=on_progress
                )
                print(f"[ModelManager] 任务创建成功: {task.id}, {task.filename}")
                
                # 启动下载
                print(f"[ModelManager] 启动下载任务: {task.id}")
                download_center.start(task.id)
                print(f"[ModelManager] 下载任务已启动")
                
                # 等待下载完成
                print(f"[ModelManager] 等待下载完成...")
                import time
                start_time = time.time()
                while task.status not in [DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED]:
                    time.sleep(1)
                    print(f"[ModelManager] 等待中... 状态: {task.status.value}, 进度: {task.progress:.1f}%")
                    if time.time() - start_time > 120:  # 增加超时时间到2分钟
                        print(f"[ModelManager] 下载超时")
                        break
                
                print(f"[ModelManager] 下载完成，状态: {task.status.value}")
                if task.error:
                    print(f"[ModelManager] 错误: {task.error}")
                
                if task.status == DownloadStatus.COMPLETED:
                    # 下载完成后，通过Ollama加载模型
                    # 首先将ggUF文件导入到Ollama
                    import subprocess
                    
                    model_path = os.path.join(save_dir, os.path.basename(model_url))
                    print(f"[ModelManager] 模型文件路径: {model_path}")
                    
                    if os.path.exists(model_path):
                        print(f"[ModelManager] 模型文件存在，大小: {os.path.getsize(model_path)} bytes")
                        # 使用ollama create命令导入模型
                        print(f"[ModelManager] 导入模型到 Ollama: {model_name}")
                        result = subprocess.run(
                            ["ollama", "create", model_name, "-f", model_path],
                            capture_output=True,
                            text=True
                        )
                        print(f"[ModelManager] 导入结果: {result.returncode}")
                        print(f"[ModelManager] 输出: {result.stdout}")
                        print(f"[ModelManager] 错误: {result.stderr}")
                        return True
                    else:
                        print(f"[ModelManager] 模型文件不存在")
                        if progress_callback:
                            progress_callback(0, 100, "错误: 模型文件不存在")
                        continue  # 尝试下一个源
                else:
                    print(f"[ModelManager] 从 {source_name} 下载失败，尝试下一个源")
                    continue  # 尝试下一个源
            
            # 所有源都失败
            if progress_callback:
                progress_callback(0, 100, "错误: 所有下载源都失败，请检查网络连接")
            return False
        except Exception as e:
            print(f"[ModelManager] 异常: {e}")
            import traceback
            traceback.print_exc()
            if progress_callback:
                progress_callback(0, 100, f"错误: {str(e)}")
            return False
    
    def load_model(self, model_info: ModelInfo) -> Optional[Any]:
        """加载模型
        
        Args:
            model_info: 模型信息
        
        Returns:
            模型客户端实例
        """
        try:
            if model_info.backend == ModelBackend.LLAMA_CPP:
                # 使用llama-cpp-python加载本地模型
                result = self.priority_loader.load_model(
                    model_path=model_info.path,
                    backend_preference=ModelBackend.LLAMA_CPP
                )
                if result.success:
                    return result.client
            elif model_info.backend == ModelBackend.OLLAMA:
                # 使用Ollama加载模型
                if self.ollama_client.is_loaded(model_info.name):
                    return self.ollama_client
                else:
                    # 尝试加载模型
                    loaded = self.ollama_client.load_model(model_info.name)
                    if loaded:
                        return self.ollama_client
            
            return None
        except Exception:
            return None
    
    def get_model_size(self, model_name: str) -> Optional[int]:
        """获取模型大小
        
        Args:
            model_name: 模型名称
        
        Returns:
            int: 模型大小（字节）
        """
        models = self.get_available_models()
        for model in models:
            if model.name == model_name and model.size:
                return model.size
        return None
    
    def is_model_available(self, model_name: str) -> bool:
        """检查模型是否可用
        
        Args:
            model_name: 模型名称
        
        Returns:
            bool: 是否可用
        """
        models = self.get_available_models()
        for model in models:
            if model.name == model_name and model.available:
                return True
        return False
    
    def get_default_model(self) -> Optional[ModelInfo]:
        """获取默认模型
        
        Returns:
            ModelInfo: 默认模型信息
        """
        # 首先检查配置中的默认模型
        default_model_name = self.config.ollama.default_model
        if default_model_name:
            models = self.get_available_models()
            for model in models:
                if model.name == default_model_name and model.available:
                    return model
        
        # 如果配置中没有默认模型或模型不可用，返回第一个可用模型
        models = self.get_available_models()
        for model in models:
            if model.available:
                return model
        
        # 如果没有可用模型，返回推荐的轻量级模型
        recommended = self._get_recommended_models()
        return recommended[0] if recommended else None
    
    def set_default_model(self, model_name: str):
        """设置默认模型
        
        Args:
            model_name: 模型名称
        """
        self.config.ollama.default_model = model_name
        from core.config import save_config
        save_config(self.config)
