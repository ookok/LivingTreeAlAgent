"""
llama-cpp-python 客户端
直接加载 GGUF 模型，无需 Ollama 中间服务
"""

import os
import sys
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Iterator, List, Callable

logger = logging.getLogger(__name__)

# 检查 llama-cpp-python 是否可用
LLAMA_CPP_AVAILABLE = False
_Llama = None

def _check_llama_cpp():
    global LLAMA_CPP_AVAILABLE, _Llama
    if LLAMA_CPP_AVAILABLE:
        return True
    try:
        from llama_cpp import Llama
        _Llama = Llama
        LLAMA_CPP_AVAILABLE = True
        return True
    except ImportError:
        return False


@dataclass
class LlamaCppConfig:
    """llama-cpp 配置"""
    # 上下文
    n_ctx: int = 4096              # 上下文窗口大小
    n_parts: int = -1             # 模型分片数 (-1 = 自动)
    n_gpu_layers: int = -1        # GPU 层数 (-1 = 自动, 0 = 仅 CPU)

    # 线程
    n_threads: int = 4            # CPU 线程数
    n_threads_batch: int = None   # 批处理线程数

    # 内存
    use_mlock: bool = True         # 锁定内存（防止换出）
    use_mmap: bool = True          # 使用内存映射文件
    no_avx: bool = False          # 禁用 AVX 指令

    # 推断
    rope_freq_base: float = 0.0   # RoPE 基础频率 (0 = 模型默认值)
    rope_freq_scale: float = 0.0  # RoPE 频率缩放
    yarn_ext_factor: float = 0.0  # YaRN 外推因子
    yarn_attn_factor: float = 0.0 # YaRN 注意力因子
    yarn_beta_fast: float = 0.0   # YaRN beta_fast
    yarn_beta_slow: float = 0.0   # YaRN beta_slow
    yarn_orig_ctx: int = 0         # YaRN 原始上下文

    # .verbose
    verbose: bool = False          # 详细输出


@dataclass
class StreamOutput:
    """流式输出"""
    delta: str = ""                # 新生成的文本
    tokens: List[int] = field(default_factory=list)  # token 列表
    done: bool = False             # 是否完成


class LlamaCppClient:
    """
    llama-cpp-python 客户端
    直接加载 GGUF 模型进行推理
    """

    def __init__(
        self,
        model_path: str,
        config: Optional[LlamaCppConfig] = None,
    ):
        """
        初始化 llama-cpp-python 客户端

        Args:
            model_path: GGUF 模型文件路径
            config: 配置选项
        """
        if not _check_llama_cpp():
            raise ImportError(
                "llama-cpp-python not installed.\n"
                "Install: pip install llama-cpp-python\n"
                "GPU: pip install llama-cpp-python --force-reinstall --no-cache-dir"
            )

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

        self.config = config or LlamaCppConfig()
        self._llama: Optional[_Llama] = None
        self._loaded = False

        # 加载模型
        self._load_model()

    def _load_model(self):
        """加载 GGUF 模型"""
        if self._loaded:
            return

        logger.info(f"Loading GGUF model: {self.model_path}")

        # 构建 kwargs
        kwargs = {
            "model_path": str(self.model_path),
            "n_ctx": self.config.n_ctx,
            "n_parts": self.config.n_parts,
            "n_gpu_layers": self.config.n_gpu_layers,
            "n_threads": self.config.n_threads,
            "use_mlock": self.config.use_mlock,
            "use_mmap": self.config.use_mmap,
            "verbose": self.config.verbose,
        }

        if self.config.n_threads_batch:
            kwargs["n_threads_batch"] = self.config.n_threads_batch

        if self.config.rope_freq_base > 0:
            kwargs["rope_freq_base"] = self.config.rope_freq_base

        if self.config.rope_freq_scale > 0:
            kwargs["rope_freq_scale"] = self.config.rope_freq_scale

        # 加载
        start = time.time()
        self._llama = _Llama(**kwargs)  # noqa: F821
        elapsed = time.time() - start

        self._loaded = True
        logger.info(f"Model loaded in {elapsed:.1f}s: {self.model_path.name}")

    def _build_prompt(
        self,
        messages: List[dict],
        system_prompt: str = "",
    ) -> str:
        """
        构建 llama.cpp 格式的提示词
        支持 Qwen、Llama 等格式
        """
        parts = []

        # 系统提示
        if system_prompt:
            parts.append(f"<|im_start|>system\n{system_prompt}<|im_end|>")

        # 消息历史
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                parts.append(f"<|im_start|>system\n{content}<|im_end|>")
            elif role == "user":
                parts.append(f"<|im_start|>user\n{content}<|im_end|>")
            elif role == "assistant":
                parts.append(f"<|im_start|>assistant\n{content}<|im_end|>")

        # 当前输入
        parts.append("<|im_start|>assistant\n")

        return "".join(parts)

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
        repeat_penalty: float = 1.1,
        stop: List[str] = None,
        echo: bool = False,
    ) -> dict:
        """
        同步生成

        Args:
            prompt: 提示词
            max_tokens: 最大 token 数
            temperature: 温度
            top_p: Top-p 采样
            top_k: Top-k 采样
            repeat_penalty: 重复惩罚
            stop: 停止词列表
            echo: 是否回显输入

        Returns:
            dict: 包含 text, usage 等信息
        """
        if not self._llama:
            raise RuntimeError("Model not loaded")

        stop = stop or []

        result = self._llama(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repeat_penalty,
            stop=stop,
            echo=echo,
            stream=False,
        )

        return result

    def stream_generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
        repeat_penalty: float = 1.1,
        stop: List[str] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> Iterator[StreamOutput]:
        """
        流式生成

        Args:
            prompt: 提示词
            max_tokens: 最大 token 数
            temperature: 温度
            top_p: Top-p 采样
            top_k: Top-k 采样
            repeat_penalty: 重复惩罚
            stop: 停止词列表
            callback: 回调函数 (token: str)

        Yields:
            StreamOutput: 流式输出
        """
        if not self._llama:
            raise RuntimeError("Model not loaded")

        stop = stop or []

        stream = self._llama(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repeat_penalty,
            stop=stop,
            echo=False,
            stream=True,
        )

        for output in stream:
            delta = ""
            if "choices" in output:
                choice = output["choices"][0]
                delta = choice.get("delta", {}).get("content", "")

            if delta:
                if callback:
                    callback(delta)
                yield StreamOutput(delta=delta)

        yield StreamOutput(done=True)

    def chat(
        self,
        messages: List[dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
        repeat_penalty: float = 1.1,
        stop: List[str] = None,
    ) -> str:
        """
        对话（同步）

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            max_tokens: 最大 token 数
            temperature: 温度
            top_p: Top-p 采样
            top_k: Top-k 采样
            repeat_penalty: 重复惩罚
            stop: 停止词列表

        Returns:
            str: 生成的回复
        """
        # 构建提示词
        prompt = self._build_prompt(messages)

        # 生成
        result = self.generate(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repeat_penalty,
            stop=stop,
        )

        return result["choices"][0]["text"]

    def stream_chat(
        self,
        messages: List[dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
        repeat_penalty: float = 1.1,
        stop: List[str] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> Iterator[str]:
        """
        对话（流式）

        Args:
            messages: 消息列表
            max_tokens: 最大 token 数
            temperature: 温度
            top_p: Top-p 采样
            top_k: Top-k 采样
            repeat_penalty: 重复惩罚
            stop: 停止词列表
            callback: 回调函数

        Yields:
            str: 生成的 token
        """
        # 构建提示词
        prompt = self._build_prompt(messages)

        # 流式生成
        for output in self.stream_generate(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repeat_penalty,
            stop=stop,
            callback=callback,
        ):
            if output.delta:
                yield output.delta

    def is_loaded(self) -> bool:
        """检查模型是否已加载"""
        return self._loaded

    def unload(self):
        """卸载模型"""
        if self._llama:
            del self._llama
            self._llama = None
            self._loaded = False
            logger.info(f"Model unloaded: {self.model_path.name}")

    def get_context_length(self) -> int:
        """获取上下文长度"""
        return self.config.n_ctx

    def get_memory_usage(self) -> dict:
        """获取内存使用情况"""
        if not self._llama:
            return {"loaded": False}

        # llama.cpp 不直接暴露内存统计
        return {
            "loaded": self._loaded,
            "model_path": str(self.model_path),
        }


# ============= 便捷函数 =============

def list_available_models(models_dir: str = "models") -> List[dict]:
    """
    列出 models 目录下的 GGUF 模型

    Args:
        models_dir: 模型目录路径

    Returns:
        List[dict]: 模型信息列表
    """
    models = []
    models_path = Path(models_dir)

    if not models_path.exists():
        return models

    for f in models_path.rglob("*"):
        if f.suffix.lower() in [".gguf", ".gguf.bin"]:
            size = f.stat().st_size
            models.append({
                "name": f.stem,
                "path": str(f.absolute()),
                "size": size,
                "size_mb": size / (1024 * 1024),
            })

    return models
