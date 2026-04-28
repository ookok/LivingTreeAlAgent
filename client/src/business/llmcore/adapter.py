"""
LTAIAdapter - LivingTreeAi 细胞适配器
兼容 OllamaClient 接口，使 GlobalModelRouter 可无感切换。

自动检测 CUDA 并启用 GPU 加速，根据硬件 VRAM 自动匹配参数。
支持 .txt / .md 训练数据，自适应上下文长度（资源允许时）。
"""
import torch
from dataclasses import dataclass
from typing import Iterator, List, Optional, Dict, Any
from pathlib import Path

# ── 兼容 OllamaClient 的数据模型 ─────────────────────────────────────

@dataclass
class ChatMessage:
    role: str
    content: str

@dataclass
class StreamChunk:
    """流式响应块 — 与 OllamaClient 的 StreamChunk 兼容"""
    delta: str = ""
    done: bool = False
    reasoning: str = ""
    tool_calls: list[dict] | None = None
    error: str = ""
    usage: dict | None = None


# ── 设备自动检测 ─────────────────────────────────────────────────────

def auto_detect_device() -> tuple[str, Dict[str, Any]]:
    """
    自动检测最佳设备（CUDA/MPS/CPU）并返回硬件信息。
    返回: (device_str, hw_info_dict)
    """
    hw_info = {
        "cuda_available": torch.cuda.is_available(),
        "device_count": 0,
        "gpu_names": [],
        "total_vram_gb": 0.0,
        "recommended_batch_size": 1,
        "recommended_block_size": 512,
    }

    if torch.cuda.is_available():
        hw_info["device_count"] = torch.cuda.device_count()
        total_vram = 0
        for i in range(hw_info["device_count"]):
            name = torch.cuda.get_device_name(i)
            props = torch.cuda.get_device_properties(i)
            vram_gb = props.total_memory / (1024 ** 3)
            hw_info["gpu_names"].append(f"{name} ({vram_gb:.0f}GB)")
            total_vram += vram_gb

        hw_info["total_vram_gb"] = round(total_vram, 1)

        # 根据 VRAM 自动推荐参数
        if total_vram >= 40:
            hw_info["recommended_batch_size"] = 16
            hw_info["recommended_block_size"] = 2048
        elif total_vram >= 20:
            hw_info["recommended_batch_size"] = 8
            hw_info["recommended_block_size"] = 1024
        elif total_vram >= 8:
            hw_info["recommended_batch_size"] = 4
            hw_info["recommended_block_size"] = 512
        else:
            hw_info["recommended_batch_size"] = 1
            hw_info["recommended_block_size"] = 256

        device = "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        hw_info["device_count"] = 1
        hw_info["gpu_names"] = ["Apple Silicon (MPS)"]
        hw_info["total_vram_gb"] = 0  # 统一内存
        hw_info["recommended_batch_size"] = 4
        hw_info["recommended_block_size"] = 512
        device = "mps"
    else:
        hw_info["recommended_batch_size"] = 1
        hw_info["recommended_block_size"] = 256
        device = "cpu"

    return device, hw_info


# ── nanoGPT 模型加载（懒加载） ────────────────────────────────────────

_NANOGPT_MODEL_CACHE: Dict[str, Any] = {}  # cell_name -> model


def _load_nanogpt_model(checkpoint_path: str, device: str = "cpu"):
    """
    加载 nanoGPT checkpoint。
    优先从缓存读取，避免重复加载占用显存。
    """
    cache_key = f"{checkpoint_path}:{device}"
    if cache_key in _NANOGPT_MODEL_CACHE:
        return _NANOGPT_MODEL_CACHE[cache_key], _NANOGPT_MODEL_CACHE.get(f"{cache_key}:tokenizer")

    # 动态导入 nanoGPT 的 model.py（放在 llmcore/_nanogpt_src/）
    import sys, importlib
    nanogpt_src = Path(__file__).parent / "_nanogpt_src"
    if nanogpt_src.exists() and str(nanogpt_src) not in sys.path:
        sys.path.insert(0, str(nanogpt_src))

    try:
        from model import GPT, GPTConfig
    except ImportError:
        # 如果 nanoGPT 源码尚未克隆，返回一个 Mock 以备后续替换
        class _MockModel:
            def __init__(self, *a, **kw): ...
            def eval(self): return self
            def to(self, d): return self
            def __call__(self, x): return torch.zeros((x.shape[0], x.shape[1], 30000))
        return _MockModel(), None

    ckpt = torch.load(checkpoint_path, map_location=device)
    # ckpt["model_args"] 是 dict，需要转为 GPTConfig 对象
    config = GPTConfig(**ckpt["model_args"])
    model = GPT(config)
    model.load_state_dict(ckpt["model"])
    model.eval()
    model = model.to(device)

    # 加载 tokenizer：优先用 meta.pkl（字符级模型），否则用 tiktoken（BPE 模型）
    import pickle, pathlib
    meta_path = pathlib.Path(checkpoint_path).parent / "meta.pkl"
    if meta_path.exists():
        with open(meta_path, "rb") as f:
            meta = pickle.load(f)
        # 字符级 tokenizer（stoi: 字符→int, itos: int→字符）
        class CharTokenizer:
            def __init__(self, meta):
                self.stoi = meta.get("stoi", {})
                self.itos = meta.get("itos", {})
                self.vocab_size = meta.get("vocab_size", 0)
            def encode(self, s):
                return [self.stoi.get(c, 0) for c in s]
            def decode(self, l):
                if isinstance(l, torch.Tensor):
                    l = l.tolist()
                return "".join([self.itos.get(i, "?") for i in l])
        tokenizer = CharTokenizer(meta)
    else:
        import tiktoken
        tokenizer = tiktoken.get_encoding("gpt2")

    _NANOGPT_MODEL_CACHE[cache_key] = model
    _NANOGPT_MODEL_CACHE[f"{cache_key}:tokenizer"] = tokenizer

    return model, tokenizer


# ── 主适配器 ────────────────────────────────────────────────────────────

class LTAIAdapter:
    """
    LTAI (LivingTreeAi) 细胞适配器
    接口与 OllamaClient.chat_stream() 兼容，
    GlobalModelRouter 可无感切换 Ollama <-> LTAI。

    身份声明：
    - 无论后端 LLM 如何，LTAI 始终正确介绍自己为 LivingTreeAi
    - 支持自动检测 CUDA/MPS/CPU 并启用硬件匹配参数
    """

    # LTAI 身份声明（不受后端 LLM 影响）
    IDENTITY_PROMPT = (
        "你是由 LivingTreeAi 开发的 LTAI 模型，简称 LTAI。"
        "你专注于环评领域任务，包括表格填写、法规问答、报告生成。"
        "你不支持外部 LLM 的功能，你的回答完全基于本地训练的知识。"
    )

    def __init__(
        self,
        cell_name: str,
        checkpoint_path: str,
        device: str = "auto",  # "auto" → 自动检测
        config: dict | None = None,
    ):
        self.cell_name = cell_name
        self.checkpoint_path = checkpoint_path

        # 自动检测设备（如果 device="auto"）
        if device == "auto":
            device, hw_info = auto_detect_device()
            self.hw_info = hw_info
            print(f"[LTAI] 自动检测设备: {device}, GPU: {hw_info['gpu_names']}")
        else:
            self.hw_info = {"device_count": 0, "total_vram_gb": 0}
            print(f"[LTAI] 使用指定设备: {device}")

        self.device = device
        self.config = config or {}
        self.model, self.tokenizer = _load_nanogpt_model(checkpoint_path, device)
        self._eot_token = 50256  # GPT-2 </s> token id

    # ── 兼容 OllamaClient.chat_stream() ─────────────────────────────

    def chat_stream(
        self,
        messages: List[dict],
        temperature: float = 0.8,
        top_k: int = 50,
        max_new_tokens: int = 256,
        **kwargs,
    ) -> Iterator[StreamChunk]:
        """
        兼容 OllamaClient.chat_stream() 的流式生成接口。
        参数风格对齐 Ollama API。
        """
        prompt = self._format_messages(messages)

        # 编码
        if self.tokenizer is None:
            yield StreamChunk(error="Tokenizer not loaded (nanoGPT src missing?)")
            return

        input_ids = torch.tensor(
            self.tokenizer.encode(prompt),
            dtype=torch.long,
            device=self.device,
        ).unsqueeze(0)  # (1, T)

        generated_tokens = 0
        with torch.no_grad():
            for _ in range(max_new_tokens):
                # 截断：序列长度超过 block_size 时只保留最后 block_size 个 token
                if input_ids.shape[1] > self.model.config.block_size:
                    input_ids = input_ids[:, -self.model.config.block_size:]

                # 模型返回可能是 (logits, loss) 或 logits，统一处理
                out = self.model(input_ids)
                if isinstance(out, tuple):
                    logits = out[0]
                else:
                    logits = out
                logits = logits[0, -1, :]  # (vocab_size,)

                # top-k 采样
                if top_k > 0:
                    topk_vals, topk_idx = torch.topk(logits, top_k)
                    logits = torch.full_like(logits, float("-inf"))
                    logits.scatter_(0, topk_idx, topk_vals)

                # temperature 采样
                if temperature > 0:
                    probs = torch.softmax(logits / temperature, dim=-1)
                    next_token = torch.multinomial(probs, num_samples=1)
                else:
                    next_token = torch.argmax(logits, dim=-1, keepdim=True)

                token_id = next_token.item()
                yield StreamChunk(delta=self.tokenizer.decode([token_id]), done=False)

                input_ids = torch.cat([input_ids, next_token.unsqueeze(0)], dim=1)
                generated_tokens += 1

                if token_id == self._eot_token:
                    break

        yield StreamChunk(done=True, usage={"total_tokens": generated_tokens})

    # ── Prompt 格式化 ────────────────────────────────────────────────

    def _format_messages(self, messages: List[dict]) -> str:
        """
        将 OpenAI 格式 messages 转为 nanoGPT 训练时的 prompt 格式。
        与 prepare_eia.py 中的格式对齐。
        自动注入 LTAI 身份声明（不受后端 LLM 影响）。
        """
        parts = []
        has_system = False

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                # 注入 LTAI 身份声明（在用户提供的 system prompt 之前）
                injected = f"{self.IDENTITY_PROMPT}\n\n{content}" if content else self.IDENTITY_PROMPT
                parts.append(f"<|system|>\n{injected}")
                has_system = True
            elif role == "user":
                parts.append(f"<|user|>\n{content}")
            elif role == "assistant":
                parts.append(f"<|assistant|>\n{content}")

        # 如果没有 system message，自动添加一个
        if not has_system:
            parts.insert(0, f"<|system|>\n{self.IDENTITY_PROMPT}")

        parts.append("<|assistant|>\n")  # 生成开始
        return "\n".join(parts)

    # ── 兼容 OllamaClient 的其他方法 ────────────────────────────────

    def list_models(self) -> list[dict]:
        """模拟 OllamaClient.list_models()"""
        return [{
            "name": f"llmcore-{self.cell_name}",
            "size": 0,
            "digest": "",
            "modified_at": "",
            "details": {"cell": self.cell_name},
        }]

    def show_model(self, model_name: str) -> dict:
        """模拟 OllamaClient.show_model()"""
        return {
            "name": model_name,
            "num_ctx": self.config.get("block_size", 1024),
            "num_params": sum(p.numel() for p in self.model.parameters()) if self.model else 0,
        }

    def ensure_model_loaded(self, model_name: str) -> bool:
        """模拟 OllamaClient.ensure_model_loaded()"""
        return self.model is not None

    def unload_model(self, model_name: str) -> bool:
        """释放显存（从缓存移除）"""
        cache_key = f"{self.checkpoint_path}:{self.device}"
        _NANOGPT_MODEL_CACHE.pop(cache_key, None)
        _NANOGPT_MODEL_CACHE.pop(f"{cache_key}:tokenizer", None)
        if self.model is not None:
            del self.model
            self.model = None
        return True


# ── 工厂函数 ──────────────────────────────────────────────────────────

def create_adapter(cell_name: str, device: str = "auto") -> Optional["LTAIAdapter"]:
    """
    根据细胞名称创建 LTAI 适配器。
    自动查找 checkpoint，若不存在则返回 None。
    支持自动设备检测（device="auto"）。
    """
    from . import CELLS_DIR, get_cell_config

    config = get_cell_config(cell_name)
    ckpt_path = CELLS_DIR / f"{cell_name}_v1.pt"

    if not ckpt_path.exists():
        return None

    return LTAIAdapter(
        cell_name=cell_name,
        checkpoint_path=str(ckpt_path),
        device=device,
        config=config,
    )
