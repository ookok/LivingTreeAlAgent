#!/usr/bin/env python3
"""
模型管理器
负责模型的检测、选择、下载和管理
"""

from core.logger import get_logger
logger = get_logger('model_manager')

import os
import json
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from core.config import AppConfig, OllamaConfig
from core.ollama_client import OllamaClient
from core.model_priority_loader import ModelBackend, LocalModelPriorityLoader

try:
    from core.config.unified_config import get_config as _get_unified_config
    _uconfig_mm = _get_unified_config()
except Exception:
    _uconfig_mm = None

def _mm_get(key: str, default):
    return _uconfig_mm.get(key, default) if _uconfig_mm else default


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
        
        # 检查本地GGUF模型（快速操作）
        local_models = self._get_local_gguf_models()
        models.extend(local_models)
        
        # 检查Ollama模型（可能会阻塞，所以放在后面）
        try:
            ollama_models = self._get_ollama_models()
            models.extend(ollama_models)
        except Exception:
            # 快速失败，避免阻塞
            pass
        
        # 检查推荐模型（快速操作）
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
                logger.info(f"[ModelManager] 本地模型不存在: {model_name}")
                return False
            
            # 加载模型
            client = self.load_model(model_info)
            if client:
                logger.info(f"[ModelManager] 成功加载本地模型: {model_name}")
                return True
            else:
                logger.info(f"[ModelManager] 加载本地模型失败: {model_name}")
                return False
        except Exception as e:
            logger.info(f"[ModelManager] 使用本地模型时出错: {e}")
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
        # 只推荐有GGUF量化版本的模型
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
                backend=ModelBackend.LLAMA_CPP,
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
            logger.info(f"[ModelManager] 开始下载模型: {model_name}")
            
            # 标记是否为 Ollama 模型的备用下载
            is_ollama_fallback = False
            
            # 检查本地是否已经有模型文件
            import os
            local_models = self._get_local_gguf_models()
            for model in local_models:
                if model.name == model_name:
                    logger.info(f"[ModelManager] 模型已存在本地: {model_name}")
                    if progress_callback:
                        progress_callback(100, 100, "模型已存在")
                    return True
            
            # 检查是否是 Ollama 模型（向量化模型等）
            ollama_models = ["nomic-embed-text", "mxbai-embed-large"]
            if model_name in ollama_models:
                # 首先尝试直接下载 GGUF 文件（优先使用 ModelScope）
                logger.info(f"[ModelManager] 尝试直接下载 GGUF 文件...")
                if progress_callback:
                    progress_callback(0, 100, "尝试下载 GGUF 文件...")
                
                # 继续使用 ModelScope 下载（如果失败再尝试 Ollama）
                # 标记为 Ollama 模型，以便后续处理
                is_ollama_fallback = True
            
            # ModelScope SDK 模型映射（使用正确的ModelScope仓库名称）
            model_downloads = {
                # L0/L1 GGUF模型
                "qwen2.5:0.5b": {
                    "modelscope_repo": "qwen/Qwen2.5-0.5B-Instruct-GGUF",
                    "gguf_file": "qwen2.5-0.5b-instruct-q4_k_m.gguf"
                },
                "qwen2.5:1.5b": {
                    "modelscope_repo": "qwen/Qwen2.5-1.5B-Instruct-GGUF",
                    "gguf_file": "qwen2.5-1.5b-instruct-q4_k_m.gguf"
                },
                "qwen2.5:3b": {
                    "modelscope_repo": "qwen/Qwen2.5-3B-Instruct-GGUF",
                    "gguf_file": "qwen2.5-3b-instruct-q4_k_m.gguf"
                },
                "qwen2.5:7b": {
                    "modelscope_repo": "qwen/Qwen2.5-7B-Instruct-GGUF",
                    "gguf_file": "qwen2.5-7b-instruct-q4_k_m.gguf"
                },
                "llama3.2:1b": {
                    "modelscope_repo": "modelscope/Llama-3.2-1B-Instruct-GGUF",
                    "gguf_file": "llama-3.2-1b-instruct-q4_k_m.gguf"
                },
                "llama3.2:3b": {
                    "modelscope_repo": "modelscope/Llama-3.2-3B-Instruct-GGUF",
                    "gguf_file": "llama-3.2-3b-instruct-q4_k_m.gguf"
                },
                # L3 向量化模型
                "nomic-embed-text": {
                    "modelscope_repo": "Embedding-GGUF/nomic-embed-text-v1.5-GGUF",
                    "gguf_file": "nomic-embed-text-v1.5-q4_k_m.gguf"
                },
                "mxbai-embed-large": {
                    "modelscope_repo": "Embedding-GGUF/mxbai-embed-large-v1-GGUF",
                    "gguf_file": "mxbai-embed-large-v1-q4_k_m.gguf"
                }
            }
            
            # 获取当前模型的下载信息
            model_info = model_downloads.get(model_name)
            if not model_info:
                logger.info(f"[ModelManager] 不支持的模型: {model_name}")
                if progress_callback:
                    progress_callback(0, 100, f"错误: 模型 {model_name} 不支持下载")
                return False
            
            # 使用 ModelScope SDK 下载
            try:
                from modelscope.hub.api import HubApi
                from modelscope.msdatasets import MsDataset
                
                logger.info(f"[ModelManager] 使用 ModelScope SDK 下载模型...")
                
                # 创建进度回调包装器
                class ModelScopeProgress:
                    def __init__(self, callback):
                        self.callback = callback
                        self.total_size = 0
                        self.downloaded_size = 0
                    
                    def update(self, bytes_transferred, total_bytes=None):
                        if total_bytes:
                            self.total_size = total_bytes
                        self.downloaded_size = bytes_transferred
                        progress = int((bytes_transferred / self.total_size) * 100) if self.total_size > 0 else 0
                        self.callback(progress, 100, f"下载中... {bytes_transferred / (1024*1024):.1f}MB / {self.total_size / (1024*1024):.1f}MB")
                
                progress = ModelScopeProgress(progress_callback) if progress_callback else None
                
                # 下载模型文件
                api = HubApi()
                local_model_dir = api.download(
                    model_id=model_info["modelscope_repo"],
                    file=[model_info["gguf_file"]],
                    destination=self._models_dir,
                    progress_callback=progress.update if progress else None
                )
                
                logger.info(f"[ModelManager] ModelScope SDK 下载完成: {local_model_dir}")
                
                # 检查下载的文件
                gguf_file_path = self._models_dir / model_info["gguf_file"]
                if gguf_file_path.exists():
                    file_size = gguf_file_path.stat().st_size
                    logger.info(f"[ModelManager] 模型文件已保存: {gguf_file_path}, 大小: {file_size / (1024*1024):.1f}MB")
                    
                    # 检查文件大小是否合理（至少100MB）
                    if file_size < 100 * 1024 * 1024:  # 100MB
                        logger.info(f"[ModelManager] 模型文件太小，可能下载不完整")
                        if progress_callback:
                            progress_callback(0, 100, "错误: 模型文件太小，下载可能不完整")
                        return False
                    
                    return True
                else:
                    logger.info(f"[ModelManager] 模型文件不存在: {gguf_file_path}")
                    if progress_callback:
                        progress_callback(0, 100, "错误: 模型文件不存在")
                    return False
                    
            except ImportError:
                logger.info(f"[ModelManager] ModelScope SDK 未安装，尝试使用其他方式...")
                # 如果 SDK 未安装，尝试使用统一下载中心
                if is_ollama_fallback:
                    # 如果是Ollama模型的备用下载，ModelScope不可用时直接尝试Ollama pull
                    logger.info(f"[ModelManager] ModelScope SDK不可用，尝试Ollama pull...")
                    if progress_callback:
                        progress_callback(0, 100, "ModelScope不可用，尝试Ollama...")
                    return self._download_ollama_model(model_name, progress_callback)
                return self._download_with_fallback(model_name, model_info, progress_callback, is_ollama_fallback=is_ollama_fallback)
            except Exception as e:
                logger.info(f"[ModelManager] ModelScope SDK 下载失败: {e}")
                # 尝试使用统一下载中心作为备选
                if is_ollama_fallback:
                    # 如果是Ollama模型的备用下载，ModelScope下载失败后尝试Ollama pull
                    logger.info(f"[ModelManager] ModelScope下载失败，尝试Ollama pull作为备用...")
                    if progress_callback:
                        progress_callback(0, 100, "ModelScope下载失败，尝试Ollama...")
                    return self._download_ollama_model(model_name, progress_callback)
                return self._download_with_fallback(model_name, model_info, progress_callback, is_ollama_fallback=is_ollama_fallback)
        except Exception as e:
            logger.info(f"[ModelManager] 异常: {e}")
            import traceback
            traceback.print_exc()
            if progress_callback:
                progress_callback(0, 100, f"错误: {str(e)}")
            return False
    
    def _download_with_fallback(self, model_name: str, model_info: dict, progress_callback=None, is_ollama_fallback=False) -> bool:
        """备用下载方法（使用HTTP下载）
        
        Args:
            is_ollama_fallback: 是否为Ollama模型的备用下载，如果是则在HTTP下载失败后尝试Ollama pull
        """
        try:
            from core.unified_downloader import get_download_center
            from core.unified_downloader import DownloadStatus, SourceType
            
            # 构建下载URL
            model_url = f"https://modelscope.cn/models/{model_info['modelscope_repo']}/resolve/master/{model_info['gguf_file']}"
            
            logger.info(f"[ModelManager] 使用备用HTTP方式下载: {model_url}")
            
            # 定义进度回调
            def on_progress(task):
                logger.info(f"[ModelManager] 进度回调: {task.status.value}, {task.progress:.1f}%")
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
            
            # 创建下载任务
            task = download_center.create_task(
                url=model_url,
                save_path=self._models_dir,
                source=SourceType.MODELSCOPE,
                source_info=model_info["modelscope_repo"],
                filename=model_info["gguf_file"],
                progress_callback=on_progress
            )
            
            # 启动下载
            download_center.start(task.id)
            
            # 等待下载完成
            import time
            start_time = time.time()
            while task.status not in [DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED]:
                time.sleep(_mm_get("delays.polling_medium", 1))
                if time.time() - start_time > _mm_get("timeouts.long", 600):  # 下载超时
                    logger.info(f"[ModelManager] 下载超时")
                    break
            
            if task.status == DownloadStatus.COMPLETED:
                gguf_file_path = self._models_dir / model_info["gguf_file"]
                if gguf_file_path.exists():
                    file_size = gguf_file_path.stat().st_size
                    logger.info(f"[ModelManager] 模型文件已保存: {gguf_file_path}, 大小: {file_size / (1024*1024):.1f}MB")
                    
                    if file_size < 100 * 1024 * 1024:  # 100MB
                        logger.info(f"[ModelManager] 模型文件太小，可能下载不完整")
                        if progress_callback:
                            progress_callback(0, 100, "错误: 模型文件太小，下载可能不完整")
                        return False
                    
                    return True
                else:
                    logger.info(f"[ModelManager] 模型文件不存在")
                    if progress_callback:
                        progress_callback(0, 100, "错误: 模型文件不存在")
                    return False
            else:
                logger.info(f"[ModelManager] 备用下载失败: {task.error}")
                if progress_callback:
                    progress_callback(0, 100, f"错误: 下载失败: {task.error or '未知错误'}")
                
                # 如果是Ollama模型的备用下载，HTTP下载也失败后尝试Ollama pull
                if is_ollama_fallback:
                    logger.info(f"[ModelManager] HTTP下载也失败了，尝试Ollama pull作为最后的备用...")
                    if progress_callback:
                        progress_callback(0, 100, "HTTP下载失败，尝试Ollama pull...")
                    return self._download_ollama_model(model_name, progress_callback)
                
                return False
                
        except Exception as e:
             logger.info(f"[ModelManager] 备用下载异常: {e}")
             if progress_callback:
                 progress_callback(0, 100, f"错误: {str(e)}")
             
             # 如果是Ollama模型的备用下载，HTTP下载异常后尝试Ollama pull
             if is_ollama_fallback:
                 logger.info(f"[ModelManager] HTTP下载异常，尝试Ollama pull作为最后的备用...")
                 if progress_callback:
                     progress_callback(0, 100, "HTTP下载异常，尝试Ollama pull...")
                 return self._download_ollama_model(model_name, progress_callback)
             
             return False
    
    def _download_ollama_model(self, model_name: str, progress_callback=None) -> bool:
        """通过ollama pull下载模型（用于向量化模型等）
        注意：只有当Ollama服务存在时才使用此方法，否则返回False让调用者尝试其他方式
        """
        try:
            import subprocess
            
            logger.info(f"[ModelManager] 尝试使用 ollama pull 下载模型: {model_name}")
            
            if progress_callback:
                progress_callback(0, 100, "正在检查 Ollama 服务...")
            
            # 检查 Ollama 服务是否运行
            try:
                check_result = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True,
                    text=True,
                    timeout=_mm_get("timeouts.quick", 10)
                )
                if check_result.returncode != 0:
                    logger.info(f"[ModelManager] Ollama 服务未运行，跳过 ollama pull")
                    if progress_callback:
                        progress_callback(0, 100, "Ollama 服务未运行，将尝试其他下载方式...")
                    return False  # 返回False，让调用者尝试其他下载方式
            except FileNotFoundError:
                logger.info(f"[ModelManager] Ollama 未安装，跳过 ollama pull")
                if progress_callback:
                    progress_callback(0, 100, "Ollama 未安装，将尝试其他下载方式...")
                return False  # 返回False，让调用者尝试其他下载方式
            except Exception as e:
                logger.info(f"[ModelManager] 检查 Ollama 服务失败: {e}，跳过 ollama pull")
                if progress_callback:
                    progress_callback(0, 100, f"Ollama 服务不可用，将尝试其他下载方式...")
                return False  # 返回False，让调用者尝试其他下载方式
            
            # 使用 ollama pull 下载模型
            process = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            for line in process.stdout:
                line = line.strip()
                if line:
                    logger.info(f"[OLLAMA] {line}")
                    
                    # 解析进度
                    if "%" in line:
                        try:
                            parts = line.split()
                            for p in parts:
                                if "%" in p:
                                    pct_str = p.replace("%", "")
                                    pct = int(float(pct_str))
                                    if progress_callback:
                                        progress_callback(pct, 100, f"下载中... {line}")
                                    break
                        except Exception as e:
                            logger.info(f"[PROGRESS PARSE ERROR] {e}")
                    elif "verifying" in line.lower():
                        if progress_callback:
                            progress_callback(99, 100, "验证中...")
                    elif "success" in line.lower():
                        if progress_callback:
                            progress_callback(100, 100, "下载完成")
            
            process.wait()
            
            if process.returncode == 0:
                logger.info(f"[ModelManager] Ollama 模型下载成功: {model_name}")
                return True
            else:
                logger.info(f"[ModelManager] Ollama 模型下载失败")
                if progress_callback:
                    progress_callback(0, 100, "错误: 下载失败")
                return False
                
        except Exception as e:
            logger.info(f"[ModelManager] Ollama 下载异常: {e}")
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
        
        # 如果没有可用模型，返回内置的L0轻量级模型
        # 这是降级方案，确保系统始终有模型可用
        l0_model = ModelInfo(
            name="qwen2.5:0.5b",
            description="内置L0轻量级模型（降级方案）",
            size=1.1e9,  # 1.1GB
            backend=ModelBackend.OLLAMA,
            available=False  # 标记为不可用，需要下载
        )
        return l0_model
    
    def set_default_model(self, model_name: str):
        """设置默认模型
        
        Args:
            model_name: 模型名称
        """
        self.config.ollama.default_model = model_name
        from core.config import save_config

        save_config(self.config)
