"""
本地模型优先级加载器
支持三种本地模型加载方式，按优先级排序：
1. vLLM (最高优先级) - 高性能推理
2. Nano-vLLM - 轻量级 vLLM 实现
3. Ollama - 简单易用的本地模型服务
4. llama-cpp-python - 直接加载 GGUF

优先使用 vLLM，因为其性能最优
"""

import os
import logging
from typing import Optional, List, Dict, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ModelBackend(Enum):
    """模型后端类型"""
    UNSLOTH = "unsloth"           # Unsloth (最高优先级)
    VLLM = "vllm"                # 标准 vLLM
    LLAMA_CPP = "llama_cpp"      # llama-cpp-python 直接加载
    NANO_VLLM = "nano_vllm"      # Nano-vLLM
    OLLAMA = "ollama"            # Ollama 服务


@dataclass
class BackendInfo:
    """后端信息"""
    backend: ModelBackend
    name: str
    available: bool
    reason: str = ""
    priority: int = 0  # 数值越高优先级越高


@dataclass
class LoadResult:
    """模型加载结果"""
    success: bool
    backend: ModelBackend
    message: str
    client: Optional[object] = None


class LocalModelPriorityLoader:
    """
    本地模型优先级加载器

    优先级顺序:
    1. Unsloth - 最高性能，4-bit量化加速 (最高优先级)
    2. vLLM - 高性能推理，支持张量并行
    3. llama-cpp-python - 直接加载 GGUF，最广泛支持
    4. Nano-vLLM - 轻量实现，API 兼容 vLLM
    5. Ollama - 简单易用 (最低优先级)
    """

    def __init__(self, models_dir: str = None):
        self.models_dir = models_dir or self._get_default_models_dir()
        self._current_backend: Optional[ModelBackend] = None
        self._client: Optional[object] = None
        self._available_backends: List[BackendInfo] = []

    def _get_default_models_dir(self) -> str:
        """获取默认模型目录"""
        from core.config import get_config_dir
        return str(get_config_dir() / "models")

    def check_backend_availability(self) -> List[BackendInfo]:
        """
        检查所有后端的可用性

        Returns:
            可用后端列表，按优先级排序
        """
        backends = []

        # 1. 检查 Unsloth (最高优先级)
        unsloth_info = self._check_unsloth()
        backends.append(unsloth_info)

        # 2. 检查 vLLM
        vllm_info = self._check_vllm()
        backends.append(vllm_info)

        # 3. 检查 llama-cpp
        llama_info = self._check_llama_cpp()
        backends.append(llama_info)

        # 4. 检查 Nano-vLLM
        nano_info = self._check_nano_vllm()
        backends.append(nano_info)

        # 5. 检查 Ollama
        ollama_info = self._check_ollama()
        backends.append(ollama_info)

        # 按优先级排序
        backends.sort(key=lambda x: x.priority, reverse=True)

        self._available_backends = backends
        return backends

    def _check_unsloth(self) -> BackendInfo:
        """检查 Unsloth 可用性"""
        info = BackendInfo(
            backend=ModelBackend.UNSLOTH,
            name="Unsloth",
            available=False,
            priority=110  # 最高优先级
        )

        try:
            import unsloth
            info.available = True
            info.reason = f"Unsloth {unsloth.__version__ if hasattr(unsloth, '__version__') else 'installed'}"
        except ImportError:
            info.reason = "Unsloth 未安装 (pip install unsloth)"
        except Exception as e:
            info.reason = f"检查失败: {e}"

        return info

    def _check_vllm(self) -> BackendInfo:
        """检查 vLLM 可用性"""
        info = BackendInfo(
            backend=ModelBackend.VLLM,
            name="vLLM",
            available=False,
            priority=100  # 第二优先级
        )
        
        try:
            import vllm
            info.available = True
            info.reason = f"vLLM {vllm.__version__ if hasattr(vllm, '__version__') else 'installed'}"
        except ImportError:
            info.reason = "vLLM 未安装 (pip install vllm)"
        except Exception as e:
            info.reason = f"检查失败: {e}"
        
        return info
    
    def _check_nano_vllm(self) -> BackendInfo:
        """检查 Nano-vLLM 可用性"""
        info = BackendInfo(
            backend=ModelBackend.NANO_VLLM,
            name="Nano-vLLM",
            available=False,
            priority=70  # 第四优先级
        )

        try:
            from core.nano_vllm import NanoVLLMClient
            info.available = True
            info.reason = "Nano-vLLM available"
        except ImportError:
            info.reason = "Nano-vLLM 模块未找到"
        except Exception as e:
            info.reason = f"检查失败: {e}"

        return info

    def _check_ollama(self) -> BackendInfo:
        """检查 Ollama 可用性"""
        info = BackendInfo(
            backend=ModelBackend.OLLAMA,
            name="Ollama",
            available=False,
            priority=50  # 最低优先级
        )
        
        try:
            import subprocess
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                info.available = True
                info.reason = "Ollama service running"
            else:
                info.reason = "Ollama service not responding"
        except FileNotFoundError:
            info.reason = "Ollama 未安装"
        except Exception as e:
            info.reason = f"检查失败: {e}"
        
        return info
    
    def _check_llama_cpp(self) -> BackendInfo:
        """检查 llama-cpp-python 可用性"""
        info = BackendInfo(
            backend=ModelBackend.LLAMA_CPP,
            name="llama-cpp-python",
            available=False,
            priority=90  # 第三优先级
        )

        try:
            from llama_cpp import Llama
            info.available = True
            info.reason = "llama-cpp-python available"
        except ImportError:
            info.reason = "llama-cpp-python 未安装"
        except Exception as e:
            info.reason = f"检查失败: {e}"

        return info

    def get_best_backend(self) -> Optional[BackendInfo]:
        """获取最佳可用后端"""
        if not self._available_backends:
            self.check_backend_availability()
        
        for backend in self._available_backends:
            if backend.available:
                return backend
        
        return None
    
    def load_model(
        self,
        model_path: str,
        backend_preference: ModelBackend = None,
        **kwargs
    ) -> LoadResult:
        """
        加载模型，优先使用指定后端（默认 vLLM）
        
        Args:
            model_path: 模型文件路径
            backend_preference: 偏好的后端类型，默认 vLLM
            **kwargs: 其他加载参数
            
        Returns:
            LoadResult 对象
        """
        if backend_preference is None:
            backend_preference = ModelBackend.UNSLOTH

        # 如果指定后端不可用，自动降级
        backends_to_try = []

        if backend_preference == ModelBackend.UNSLOTH:
            backends_to_try = [ModelBackend.UNSLOTH, ModelBackend.VLLM, ModelBackend.LLAMA_CPP, ModelBackend.NANO_VLLM, ModelBackend.OLLAMA]
        elif backend_preference == ModelBackend.VLLM:
            backends_to_try = [ModelBackend.VLLM, ModelBackend.UNSLOTH, ModelBackend.LLAMA_CPP, ModelBackend.NANO_VLLM, ModelBackend.OLLAMA]
        elif backend_preference == ModelBackend.LLAMA_CPP:
            backends_to_try = [ModelBackend.LLAMA_CPP, ModelBackend.UNSLOTH, ModelBackend.VLLM, ModelBackend.NANO_VLLM, ModelBackend.OLLAMA]
        elif backend_preference == ModelBackend.NANO_VLLM:
            backends_to_try = [ModelBackend.NANO_VLLM, ModelBackend.LLAMA_CPP, ModelBackend.UNSLOTH, ModelBackend.VLLM, ModelBackend.OLLAMA]
        elif backend_preference == ModelBackend.OLLAMA:
            backends_to_try = [ModelBackend.OLLAMA, ModelBackend.NANO_VLLM, ModelBackend.LLAMA_CPP, ModelBackend.VLLM, ModelBackend.UNSLOTH]
        else:
            backends_to_try = [ModelBackend.UNSLOTH, ModelBackend.VLLM, ModelBackend.LLAMA_CPP, ModelBackend.NANO_VLLM, ModelBackend.OLLAMA]
        
        # 检查可用性并尝试加载
        for backend in backends_to_try:
            info = self._check_backend(backend)
            if info.available:
                result = self._try_load(backend, model_path, **kwargs)
                if result.success:
                    self._current_backend = backend
                    self._client = result.client
                    return result
                else:
                    logger.warning(f"{backend.value} 加载失败: {result.message}，尝试下一个后端...")
        
        return LoadResult(
            success=False,
            backend=backend_preference,
            message="所有后端都无法加载模型"
        )
    
    def _check_backend(self, backend: ModelBackend) -> BackendInfo:
        """检查指定后端的可用性"""
        if backend == ModelBackend.UNSLOTH:
            return self._check_unsloth()
        elif backend == ModelBackend.VLLM:
            return self._check_vllm()
        elif backend == ModelBackend.LLAMA_CPP:
            return self._check_llama_cpp()
        elif backend == ModelBackend.NANO_VLLM:
            return self._check_nano_vllm()
        elif backend == ModelBackend.OLLAMA:
            return self._check_ollama()
        else:
            return self._check_llama_cpp()
    
    def _try_load(self, backend: ModelBackend, model_path: str, **kwargs) -> LoadResult:
        """尝试使用指定后端加载模型"""

        if backend == ModelBackend.UNSLOTH:
            return self._load_with_unsloth(model_path, **kwargs)
        elif backend == ModelBackend.VLLM:
            return self._load_with_vllm(model_path, **kwargs)
        elif backend == ModelBackend.LLAMA_CPP:
            return self._load_with_llama_cpp(model_path, **kwargs)
        elif backend == ModelBackend.NANO_VLLM:
            return self._load_with_nano_vllm(model_path, **kwargs)
        elif backend == ModelBackend.OLLAMA:
            return self._load_with_ollama(model_path, **kwargs)
        else:
            return self._load_with_llama_cpp(model_path, **kwargs)

    def _load_with_unsloth(self, model_path: str, **kwargs) -> LoadResult:
        """使用 Unsloth 加载"""
        try:
            from unsloth import FastLanguageModel

            # 获取模型参数
            max_seq_length = kwargs.get("max_seq_length", 4096)
            dtype = kwargs.get("dtype", None)
            load_in_4bit = kwargs.get("load_in_4bit", True)

            # 加载模型
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=model_path,
                max_seq_length=max_seq_length,
                dtype=dtype,
                load_in_4bit=load_in_4bit,
            )

            # 启用推理模式
            FastLanguageModel.for_inference(model)

            # 返回包装对象
            class UnslothModelWrapper:
                def __init__(self, model, tokenizer):
                    self.model = model
                    self.tokenizer = tokenizer

                def chat(self, messages, **kwargs):
                    # 简单的 chat 接口实现
                    from .unified_model_client import ChatMessage, StreamChunk
                    prompt = "\n".join([f"{m.role}: {m.content}" for m in messages])
                    prompt += "\nassistant:"

                    inputs = self.tokenizer(prompt, return_tensors="pt").to("cuda")
                    outputs = self.model.generate(**inputs, max_new_tokens=kwargs.get("max_tokens", 256))
                    text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                    yield StreamChunk(delta=text, done=True)

                def chat_stream(self, messages, config):
                    # 流式接口
                    for chunk in self.chat(messages, max_tokens=config.max_tokens):
                        yield chunk

            return LoadResult(
                success=True,
                backend=ModelBackend.UNSLOTH,
                message="Unsloth 加载成功",
                client=UnslothModelWrapper(model, tokenizer)
            )
        except Exception as e:
            return LoadResult(
                success=False,
                backend=ModelBackend.UNSLOTH,
                message=f"Unsloth 加载失败: {e}"
            )

    def _load_with_vllm(self, model_path: str, **kwargs) -> LoadResult:
        """使用 vLLM 加载"""
        try:
            from vllm import LLM, SamplingParams
            
            tensor_parallel = kwargs.get("tensor_parallel_size", 1)
            gpu_memory_utilization = kwargs.get("gpu_memory_utilization", 0.9)
            max_model_len = kwargs.get("max_model_len", 4096)
            
            llm = LLM(
                model=model_path,
                tensor_parallel_size=tensor_parallel,
                gpu_memory_utilization=gpu_memory_utilization,
                max_model_len=max_model_len,
                trust_remote_code=True,
            )
            
            return LoadResult(
                success=True,
                backend=ModelBackend.VLLM,
                message="vLLM 加载成功",
                client=llm
            )
        except Exception as e:
            return LoadResult(
                success=False,
                backend=ModelBackend.VLLM,
                message=f"vLLM 加载失败: {e}"
            )
    
    def _load_with_nano_vllm(self, model_path: str, **kwargs) -> LoadResult:
        """使用 Nano-vLLM 加载"""
        try:
            from core.nano_vllm import NanoVLLMClient
            
            port = kwargs.get("port", 8000)
            host = kwargs.get("host", "localhost")
            
            client = NanoVLLMClient(
                model_path=model_path,
                port=port,
                host=host,
                tensor_parallel_size=kwargs.get("tensor_parallel_size", 1),
                gpu_memory_utilization=kwargs.get("gpu_memory_utilization", 0.9),
                max_model_len=kwargs.get("max_model_len", 4096),
            )
            
            # 检查服务是否成功启动
            if not client.start_server():
                return LoadResult(
                    success=False,
                    backend=ModelBackend.NANO_VLLM,
                    message="Nano-vLLM 服务启动失败"
                )
            
            return LoadResult(
                success=True,
                backend=ModelBackend.NANO_VLLM,
                message="Nano-vLLM 加载成功",
                client=client
            )
        except Exception as e:
            return LoadResult(
                success=False,
                backend=ModelBackend.NANO_VLLM,
                message=f"Nano-vLLM 加载失败: {e}"
            )
    
    def _load_with_ollama(self, model_path: str, **kwargs) -> LoadResult:
        """使用 Ollama 加载"""
        try:
            from core.ollama_client import OllamaClient
            from core.config import OllamaConfig
            import subprocess
            import os
            
            # 使用简单的模型名称
            model_name = "local-model"
            
            config = OllamaConfig()
            client = OllamaClient(config)
            
            # 检查模型是否存在于 Ollama
            models = client.list_models()
            model_exists = any(m.name == model_name for m in models)
            
            if not model_exists:
                # 如果模型不存在，使用 ollama create 命令创建
                print(f"[ModelLoader] 在 Ollama 中创建模型: {model_name}")
                # 创建临时 Modelfile
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write(f"FROM {model_path}")
                    modelfile_path = f.name
                
                try:
                    result = subprocess.run(
                        ["ollama", "create", model_name, "-f", modelfile_path],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        return LoadResult(
                            success=False,
                            backend=ModelBackend.OLLAMA,
                            message=f"Ollama 创建模型失败: {result.stderr}"
                        )
                finally:
                    # 清理临时文件
                    import os
                    if os.path.exists(modelfile_path):
                        os.unlink(modelfile_path)
            
            # 加载模型
            if not client.is_loaded(model_name):
                client.load_model(model_name)
            
            return LoadResult(
                success=True,
                backend=ModelBackend.OLLAMA,
                message=f"Ollama 加载成功 ({model_name})",
                client=client
            )
        except Exception as e:
            return LoadResult(
                success=False,
                backend=ModelBackend.OLLAMA,
                message=f"Ollama 加载失败: {e}"
            )
    
    def _load_with_llama_cpp(self, model_path: str, **kwargs) -> LoadResult:
        """使用 llama-cpp-python 加载"""
        try:
            from llama_cpp import Llama
            
            llm = Llama(
                model_path=model_path,
                n_ctx=kwargs.get("n_ctx", 4096),
                n_threads=kwargs.get("n_threads", 4),
                n_gpu_layers=kwargs.get("n_gpu_layers", -1),
                use_mlock=kwargs.get("use_mlock", True),
                use_mmap=kwargs.get("use_mmap", True),
            )
            
            return LoadResult(
                success=True,
                backend=ModelBackend.LLAMA_CPP,
                message="llama-cpp-python 加载成功",
                client=llm
            )
        except Exception as e:
            return LoadResult(
                success=False,
                backend=ModelBackend.LLAMA_CPP,
                message=f"llama-cpp-python 加载失败: {e}"
            )
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        **kwargs
    ) -> Optional[str]:
        """使用当前加载的模型生成文本"""
        if self._client is None:
            logger.error("No model loaded")
            return None

        try:
            if self._current_backend == ModelBackend.UNSLOTH:
                # Unsloth 使用 transformers
                inputs = self._client.tokenizer(prompt, return_tensors="pt").to("cuda")
                outputs = self._client.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                )
                return self._client.tokenizer.decode(outputs[0], skip_special_tokens=True)

            elif self._current_backend == ModelBackend.VLLM:
                from vllm import SamplingParams
                sampling_params = SamplingParams(
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                outputs = self._client.generate(prompt, sampling_params)
                return outputs[0].outputs[0].text

            elif self._current_backend == ModelBackend.NANO_VLLM:
                from core.nano_vllm import SamplingParams
                sampling_params = SamplingParams(
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                result = self._client.generate([prompt], sampling_params)
                return result[0].text if result else None

            elif self._current_backend == ModelBackend.OLLAMA:
                return self._client.generate(
                    self._client.config.default_model,
                    prompt
                )

            elif self._current_backend == ModelBackend.LLAMA_CPP:
                output = self._client(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                )
                return output["choices"][0]["text"]

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return None
    
    def get_current_backend(self) -> Optional[ModelBackend]:
        """获取当前使用后端"""
        return self._current_backend
    
    def get_available_backends(self) -> List[BackendInfo]:
        """获取所有可用后端"""
        return self._available_backends
    
    def unload_model(self):
        """卸载模型"""
        if self._client:
            try:
                if self._current_backend == ModelBackend.UNSLOTH:
                    del self._client.model
                    del self._client.tokenizer
                elif self._current_backend == ModelBackend.NANO_VLLM:
                    self._client.stop_server()
                elif self._current_backend == ModelBackend.OLLAMA:
                    pass
                else:
                    del self._client
            except Exception as e:
                logger.error(f"Unload error: {e}")

            self._client = None
            self._current_backend = None


# 全局单例
_loader: Optional[LocalModelPriorityLoader] = None


def get_priority_loader() -> LocalModelPriorityLoader:
    """获取优先级加载器单例"""
    global _loader
    if _loader is None:
        _loader = LocalModelPriorityLoader()
    return _loader


def load_model_with_priority(
    model_path: str,
    backend: ModelBackend = None,
    **kwargs
) -> LoadResult:
    """快捷函数：使用优先级加载模型"""
    return get_priority_loader().load_model(model_path, backend, **kwargs)


def check_local_model_backends() -> List[BackendInfo]:
    """快捷函数：检查所有后端可用性"""
    return get_priority_loader().check_backend_availability()
