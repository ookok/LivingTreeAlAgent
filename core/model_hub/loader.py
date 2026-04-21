# -*- coding: utf-8 -*-
"""
多后端模型加载适配器 (Model Loader)

兼容主流模型加载工具:
1. Ollama     - 通过 REST API 调用本地 Ollama 服务
2. llama_cpp  - 通过 llama-cpp-python 加载 GGUF 模型
3. vLLM       - 通过 vLLM Python API 加载模型 (兼容 OpenAI API)
4. Unsloth    - 通过 Unsloth 快速加载 HuggingFace 模型
5. Transformers - 通过 HuggingFace Transformers 原生加载
"""

from __future__ import annotations

import os
import json
import logging
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any, List, Dict
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class LoadBackend(Enum):
    """加载后端枚举"""
    OLLAMA = "ollama"
    LLAMA_CPP = "llama_cpp"
    VLLM = "vllm"
    UNSLOTH = "unsloth"
    TRANSFORMERS = "transformers"
    AUTO = "auto"


@dataclass
class LoadConfig:
    """模型加载配置"""
    # 加载后端 (auto 为自动检测)
    backend: str = "auto"
    # 模型路径 (本地路径或 repo_id)
    model_path: str = ""
    # 模型名 (用于 Ollama / HF repo_id)
    model_name: str = ""
    # GGUF 文件路径 (用于 llama_cpp)
    gguf_file: str = ""
    # Ollama 服务地址
    ollama_host: str = "http://localhost:11434"
    # vLLM 服务地址
    vllm_host: str = "http://localhost:8000"
    # 推理精度
    dtype: str = "auto"
    # 上下文长度
    context_size: int = 4096
    # GPU 层数 (llama_cpp)
    gpu_layers: int = -1
    # 批大小
    batch_size: int = 512
    # 线程数 (llama_cpp CPU 推理)
    n_threads: int = 4
    # 是否启用 Flash Attention
    use_flash_attn: bool = True
    # Ollama pull
    ollama_pull: bool = True
    # vLLM 参数
    vllm_port: int = 8000
    vllm_tensor_parallel_size: int = 1
    # Unsloth 参数
    unsloth_load_in_4bit: bool = True
    unsloth_max_seq_length: int = 4096
    # 额外参数 (传递给底层加载器)
    extra_kwargs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadResult:
    """模型加载结果"""
    backend: str
    model_id: str = ""
    status: str = "success"  # success, failed, partial
    message: str = ""
    success: bool = True
    model_ref: Any = None  # 实际加载的模型对象
    model_path: str = ""  # 模型本地路径
    config: Optional[LoadConfig] = None
    supports_generate: bool = True
    supports_stream: bool = True
    supports_chat: bool = True

    @property
    def error(self) -> str:
        """别名: error → message (向后兼容)"""
        return self.message

    @error.setter
    def error(self, value: str):
        self.message = value

    def to_dict(self) -> dict:
        return {
            "backend": self.backend,
            "model_id": self.model_id,
            "status": self.status,
            "success": self.success,
            "message": self.message,
            "supports_generate": self.supports_generate,
            "supports_stream": self.supports_stream,
            "supports_chat": self.supports_chat,
        }


class LoaderBase(ABC):
    """加载器基类"""

    @property
    @abstractmethod
    def backend_name(self) -> str: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def load(self, config: LoadConfig) -> LoadResult: ...

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str: ...

    def unload(self):
        """卸载模型 (可选覆盖)"""
        pass

    def check_gguf_file(self, model_dir: str) -> Optional[str]:
        """在目录中查找 GGUF 文件"""
        if not os.path.isdir(model_dir):
            return None
        for f in os.listdir(model_dir):
            if f.lower().endswith(".gguf"):
                return os.path.join(model_dir, f)
        return None


class OllamaLoader(LoaderBase):
    """Ollama 后端加载器"""

    def __init__(self):
        self._model_name: Optional[str] = None
        self._host = "http://localhost:11434"

    @property
    def backend_name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        try:
            import httpx
            resp = httpx.get(f"{self._host}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def load(self, config: LoadConfig) -> LoadResult:
        try:
            import httpx
        except ImportError:
            # 回退到 urllib
            import urllib.request, urllib.error
            return self._load_urllib(config)

        model_name = config.model_name or config.model_path
        if not model_name:
            return LoadResult(success=False, backend=self.backend_name, error="Ollama 需要 model_name")

        self._host = config.ollama_host

        # 检查模型是否已存在
        try:
            resp = httpx.get(f"{config.ollama_host}/api/tags", timeout=10)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]
            model_exists = model_name in model_names or any(model_name in n for n in model_names)
        except Exception:
            model_exists = False

        if model_exists:
            self._model_name = model_name
            return LoadResult(success=True, backend=self.backend_name, model_id=model_name,
                              message=f"Ollama 模型 '{model_name}' 已就绪", config=config)

        # 尝试从 GGUF 导入
        if config.gguf_file and os.path.exists(config.gguf_file):
            try:
                modelfile = f'FROM {config.gguf_file}\nPARAMETER num_ctx {config.context_size}'
                resp = httpx.post(f"{config.ollama_host}/api/create",
                                  json={"name": model_name, "modelfile": modelfile, "stream": False},
                                  timeout=120)
                resp.raise_for_status()
                self._model_name = model_name
                return LoadResult(success=True, backend=self.backend_name, model_id=model_name,
                                  message=f"已从 GGUF 导入 Ollama 模型 '{model_name}'", config=config)
            except Exception as e:
                return LoadResult(success=False, backend=self.backend_name, error=f"导入 GGUF 失败: {e}")

        # 尝试 pull
        if config.ollama_pull and (":" in model_name or "/" not in model_name):
            logger.info(f"[Ollama] 正在 pull 模型: {model_name}")
            try:
                resp = httpx.post(f"{config.ollama_host}/api/pull",
                                  json={"name": model_name, "stream": False}, timeout=600)
                resp.raise_for_status()
                self._model_name = model_name
                return LoadResult(success=True, backend=self.backend_name, model_id=model_name,
                                  message=f"已 pull 模型 '{model_name}'", config=config)
            except Exception as e:
                return LoadResult(success=False, backend=self.backend_name, error=f"Ollama pull 失败: {e}")

        return LoadResult(success=False, backend=self.backend_name,
                          error=f"无法加载模型 '{model_name}', 请确认模型名正确或指定 gguf_file")

    def _load_urllib(self, config: LoadConfig) -> LoadResult:
        """不依赖 httpx 的加载方式"""
        import urllib.request

        model_name = config.model_name or config.model_path
        if not model_name:
            return LoadResult(success=False, backend=self.backend_name, error="Ollama 需要 model_name")

        host = config.ollama_host
        self._host = host

        try:
            req = urllib.request.Request(f"{host}/api/tags", headers={"User-Agent": "LivingTreeAI"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            return LoadResult(success=False, backend=self.backend_name,
                              error=f"Ollama 服务不可用: {e}")

        # 尝试 pull
        if config.ollama_pull:
            try:
                data = json.dumps({"name": model_name, "stream": False}).encode()
                req = urllib.request.Request(f"{host}/api/pull", data=data,
                                             headers={"Content-Type": "application/json", "User-Agent": "LivingTreeAI"})
                urllib.request.urlopen(req, timeout=600)
                self._model_name = model_name
                return LoadResult(success=True, backend=self.backend_name, model_id=model_name,
                                  message=f"已 pull 模型 '{model_name}'", config=config)
            except Exception as e:
                return LoadResult(success=False, backend=self.backend_name, error=f"Ollama pull 失败: {e}")

        return LoadResult(success=False, backend=self.backend_name, error="无法加载模型")

    def generate(self, prompt: str, **kwargs) -> str:
        if not self._model_name:
            raise RuntimeError("没有已加载的模型")
        try:
            import httpx
            resp = httpx.post(f"{self._host}/api/generate", json={
                "model": self._model_name, "prompt": prompt, "stream": False,
                "options": {"num_ctx": kwargs.get("context_size", 4096),
                            "temperature": kwargs.get("temperature", 0.7)},
            }, timeout=120)
            resp.raise_for_status()
            return resp.json().get("response", "")
        except ImportError:
            import urllib.request
            data = json.dumps({"model": self._model_name, "prompt": prompt, "stream": False}).encode()
            req = urllib.request.Request(f"{self._host}/api/generate", data=data,
                                         headers={"Content-Type": "application/json", "User-Agent": "LivingTreeAI"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read()).get("response", "")

    def unload(self):
        self._model_name = None


class LlamaCppLoader(LoaderBase):
    """llama-cpp-python 后端加载器"""

    def __init__(self):
        self._model = None

    @property
    def backend_name(self) -> str:
        return "llama_cpp"

    def is_available(self) -> bool:
        try:
            from llama_cpp import Llama
            return True
        except ImportError:
            return False

    def load(self, config: LoadConfig) -> LoadResult:
        model_path = config.gguf_file or config.model_path
        if not model_path:
            return LoadResult(success=False, backend=self.backend_name, error="llama_cpp 需要 model_path 或 gguf_file")
        if not os.path.exists(model_path):
            return LoadResult(success=False, backend=self.backend_name, error=f"模型文件不存在: {model_path}")

        try:
            from llama_cpp import Llama
            kwargs = {
                "model_path": model_path,
                "n_ctx": config.context_size,
                "n_gpu_layers": config.gpu_layers,
                "n_threads": config.n_threads,
                "verbose": False,
            }
            kwargs.update(config.extra_kwargs)
            self._model = Llama(**kwargs)
            return LoadResult(success=True, backend=self.backend_name, model_id=model_path,
                              message=f"llama_cpp 加载成功: {model_path}",
                              model_ref=self._model, config=config)
        except Exception as e:
            return LoadResult(success=False, backend=self.backend_name, error=f"llama_cpp 加载失败: {e}")

    def generate(self, prompt: str, **kwargs) -> str:
        if self._model is None:
            raise RuntimeError("模型未加载")
        result = self._model(prompt, max_tokens=kwargs.get("max_tokens", 512),
                             temperature=kwargs.get("temperature", 0.7),
                             stop=kwargs.get("stop", None))
        return result["choices"][0]["text"]

    def unload(self):
        if self._model is not None:
            del self._model
            self._model = None


class VllmLoader(LoaderBase):
    """vLLM 后端加载器"""

    def __init__(self):
        self._host = "http://localhost:8000"
        self._model_name: Optional[str] = None

    @property
    def backend_name(self) -> str:
        return "vllm"

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                [sys.executable, "-c", "import vllm; print('ok')"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def load(self, config: LoadConfig) -> LoadResult:
        model_path = config.model_path or config.model_name
        if not model_path:
            return LoadResult(success=False, backend=self.backend_name, error="vLLM 需要 model_path 或 model_name")

        # 尝试直接导入 vLLM LLM
        try:
            from vllm import LLM
            engine = LLM(model=model_path, dtype=config.dtype, trust_remote_code=True)
            return LoadResult(success=True, backend=self.backend_name, model_id=model_path,
                              model_ref=engine, config=config)
        except Exception:
            pass

        # 回退: 启动 vLLM server
        try:
            cmd = [
                sys.executable, "-m", "vllm.entrypoints.openai.api_server",
                "--model", model_path,
                "--host", config.vllm_host,
                "--port", str(config.vllm_port),
                "--trust-remote-code",
            ]
            if config.vllm_tensor_parallel_size > 1:
                cmd.extend(["--tensor-parallel-size", str(config.vllm_tensor_parallel_size)])

            logger.info(f"[vLLM] 启动服务器: {' '.join(cmd)}")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0)
            self._host = f"http://{config.vllm_host}:{config.vllm_port}"
            self._model_name = model_path
            return LoadResult(success=True, backend=self.backend_name, model_id=model_path,
                              message=f"vLLM 服务器已启动 @ {self._host}", config=config)
        except Exception as e:
            return LoadResult(success=False, backend=self.backend_name, error=f"vLLM 启动失败: {e}")

    def generate(self, prompt: str, **kwargs) -> str:
        if not self._model_name:
            raise RuntimeError("模型未加载")
        import urllib.request
        data = json.dumps({
            "model": self._model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 512),
        }).encode()
        req = urllib.request.Request(f"{self._host}/v1/chat/completions", data=data,
                                     headers={"Content-Type": "application/json", "User-Agent": "LivingTreeAI"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]

    def unload(self):
        self._model_name = None


class UnslothLoader(LoaderBase):
    """Unsloth 快速加载器"""

    def __init__(self):
        self._model = None
        self._tokenizer = None

    @property
    def backend_name(self) -> str:
        return "unsloth"

    def is_available(self) -> bool:
        try:
            import unsloth
            return True
        except ImportError:
            return False

    def load(self, config: LoadConfig) -> LoadResult:
        model_path = config.model_path or config.model_name
        if not model_path:
            return LoadResult(success=False, backend=self.backend_name, error="Unsloth 需要 model_path 或 model_name")

        try:
            from unsloth import FastLanguageModel
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=model_path,
                max_seq_length=config.unsloth_max_seq_length,
                load_in_4bit=config.unsloth_load_in_4bit,
            )
            FastLanguageModel.for_inference(model)
            self._model = model
            self._tokenizer = tokenizer
            return LoadResult(success=True, backend=self.backend_name, model_id=model_path,
                              model_ref=(model, tokenizer), config=config)
        except Exception as e:
            return LoadResult(success=False, backend=self.backend_name, error=f"Unsloth 加载失败: {e}")

    def generate(self, prompt: str, **kwargs) -> str:
        if self._model is None or self._tokenizer is None:
            raise RuntimeError("模型未加载")
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
        outputs = self._model.generate(**inputs, max_new_tokens=kwargs.get("max_tokens", 512),
                                       temperature=kwargs.get("temperature", 0.7), use_cache=True)
        return self._tokenizer.decode(outputs[0], skip_special_tokens=True)

    def unload(self):
        if self._model is not None:
            del self._model
            self._model = None
        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None


class TransformersLoader(LoaderBase):
    """HuggingFace Transformers 原生加载器"""

    def __init__(self):
        self._model = None
        self._tokenizer = None

    @property
    def backend_name(self) -> str:
        return "transformers"

    def is_available(self) -> bool:
        try:
            import transformers
            return True
        except ImportError:
            return False

    def load(self, config: LoadConfig) -> LoadResult:
        model_path = config.model_path or config.model_name
        if not model_path:
            return LoadResult(success=False, backend=self.backend_name, error="Transformers 需要 model_path 或 model_name")

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                model_path, torch_dtype="auto", device_map="auto", trust_remote_code=True,
            )
            self._model = model
            self._tokenizer = tokenizer
            return LoadResult(success=True, backend=self.backend_name, model_id=model_path,
                              model_ref=(model, tokenizer), config=config)
        except Exception as e:
            return LoadResult(success=False, backend=self.backend_name, error=f"Transformers 加载失败: {e}")

    def generate(self, prompt: str, **kwargs) -> str:
        if self._model is None or self._tokenizer is None:
            raise RuntimeError("模型未加载")
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
        outputs = self._model.generate(**inputs, max_new_tokens=kwargs.get("max_tokens", 512),
                                       temperature=kwargs.get("temperature", 0.7))
        return self._tokenizer.decode(outputs[0], skip_special_tokens=True)

    def unload(self):
        if self._model is not None:
            del self._model
            self._model = None
        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None


class ModelLoader:
    """
    统一模型加载器 - 自动选择可用的加载后端
    """

    _BACKEND_MAP: Dict[str, type] = {
        "ollama": OllamaLoader,
        "llama_cpp": LlamaCppLoader,
        "vllm": VllmLoader,
        "unsloth": UnslothLoader,
        "transformers": TransformersLoader,
    }

    BACKEND_DESCRIPTIONS = {
        "ollama": "通过 Ollama REST API 推理 (需 Ollama 服务)",
        "llama_cpp": "直接加载 GGUF 模型本地推理 (需 llama-cpp-python)",
        "vllm": "高性能批量推理 (需 vllm + GPU)",
        "unsloth": "基于 Transformers 快速加载 (需 unsloth)",
        "transformers": "HuggingFace Transformers 原生加载 (需 transformers)",
    }

    def __init__(self):
        self._loaders: Dict[str, LoaderBase] = {
            "ollama": OllamaLoader(),
            "llama_cpp": LlamaCppLoader(),
            "vllm": VllmLoader(),
            "unsloth": UnslothLoader(),
            "transformers": TransformersLoader(),
        }
        self._active_loader: Optional[LoaderBase] = None
        self._active_result: Optional[LoadResult] = None

    def get_available_backends(self) -> List[dict]:
        """列出所有可用后端"""
        return [
            {
                "name": name,
                "class": loader.__class__.__name__,
                "available": loader.is_available(),
                "description": self.BACKEND_DESCRIPTIONS.get(name, ""),
            }
            for name, loader in self._loaders.items()
        ]

    def list_backends(self) -> List[dict]:
        """别名"""
        return self.get_available_backends()

    def detect_backend(self, model_path: str = "", config: Optional[LoadConfig] = None) -> str:
        """
        自动检测最适合的加载后端

        支持两种调用方式:
        - detect_backend(model_path) - 简单模式
        - detect_backend(config=LoadConfig(...)) - 配置模式
        """
        if config and config.backend != "auto":
            return config.backend

        path = model_path or (config.model_path if config else "") or (config.model_name if config else "")

        # GGUF 文件 → llama_cpp
        if path and path.lower().endswith(".gguf"):
            if self._loaders["llama_cpp"].is_available():
                return "llama_cpp"

        # Ollama tag 格式
        if path and ":" in path and "/" not in path:
            if self._loaders["ollama"].is_available():
                return "ollama"

        # 目录中含 GGUF
        if path and os.path.isdir(path):
            gguf = self._loaders["llama_cpp"].check_gguf_file(path)
            if gguf and self._loaders["llama_cpp"].is_available():
                return "llama_cpp"

        # 按优先级检测服务类后端
        for backend_name in ["ollama", "vllm", "unsloth", "transformers"]:
            if self._loaders[backend_name].is_available():
                return backend_name

        return "transformers"

    def load(self, config: LoadConfig) -> LoadResult:
        """加载模型"""
        backend_name = config.backend
        if backend_name == "auto":
            backend_name = self.detect_backend(config=config)

        if backend_name not in self._loaders:
            return LoadResult(success=False, backend=backend_name,
                              error=f"未知后端: {backend_name}")

        loader = self._loaders[backend_name]
        result = loader.load(config)
        if result.success:
            self._active_loader = loader
            self._active_result = result
        return result

    def generate(self, prompt: str, **kwargs) -> str:
        """使用当前加载的模型生成文本"""
        if self._active_loader is None:
            raise RuntimeError("没有已加载的模型, 请先调用 load()")
        return self._active_loader.generate(prompt, **kwargs)

    def unload(self):
        """卸载当前模型"""
        if self._active_loader is not None:
            self._active_loader.unload()
            self._active_loader = None
            self._active_result = None
