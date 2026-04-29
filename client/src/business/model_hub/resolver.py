# -*- coding: utf-8 -*-
"""
模型名解析器 (Model Resolver)
支持模糊匹配、多源搜索、相似推荐
from __future__ import annotations
"""


import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ModelSource(Enum):
    """模型来源"""
    MODELSCOPE = "modelscope"
    HUGGINGFACE = "huggingface"
    GITHUB = "github"
    OLLAMA_REGISTRY = "ollama_registry"
    LOCAL = "local"
    UNKNOWN = "unknown"


@dataclass
class ModelMatchResult:
    """模型匹配结果"""
    # 标准化后的模型名
    model_id: str
    # 模型显示名
    display_name: str
    # 来源平台
    source: ModelSource
    # 匹配精确度 (0.0 ~ 1.0)
    confidence: float
    # 模型下载 URL (如果有)
    download_url: Optional[str] = None
    # 文件大小 (bytes, 估算)
    file_size: int = 0
    # 模型格式 (gguf / safetensors / bin 等)
    file_format: str = ""
    # 附加信息
    tags: list[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "source": self.source.value,
            "confidence": round(self.confidence, 3),
            "download_url": self.download_url,
            "file_size": self.file_size,
            "file_format": self.file_format,
            "tags": self.tags,
            "description": self.description,
        }


class ModelResolver:
    """
    模型名解析器

    功能:
    1. 标准化模型名 (qwen2.5:0.5b → Qwen/Qwen2.5-0.5B)
    2. 模糊匹配 (支持常见缩写和变体)
    3. 调用多源搜索获取精确匹配
    4. 找不到精确匹配时返回相似推荐
    """

    # 常见模型别名映射: alias → canonical
    _ALIAS_MAP: dict[str, str] = {
        # Qwen 系列
        "qwen": "Qwen/Qwen2.5-7B-Instruct",
        "qwen2": "Qwen/Qwen2-7B-Instruct",
        "qwen2.5": "Qwen/Qwen2.5-7B-Instruct",
        "qwen3": "Qwen/Qwen3-8B",
        # LLaMA 系列
        "llama": "meta-llama/Llama-3.1-8B-Instruct",
        "llama3": "meta-llama/Llama-3.1-8B-Instruct",
        "llama3.1": "meta-llama/Llama-3.1-8B-Instruct",
        "llama4": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        # Mistral 系列
        "mistral": "mistralai/Mistral-7B-Instruct-v0.3",
        "mistral-large": "mistralai/Mistral-Large-Instruct-2411",
        "codestral": "mistralai/Codestral-22B-v0.1",
        # Gemma 系列
        "gemma": "google/gemma-2-9b-it",
        "gemma2": "google/gemma-2-9b-it",
        "gemma3": "google/gemma-3-27b-it",
        # DeepSeek 系列
        "deepseek": "deepseek-ai/DeepSeek-V3",
        "deepseek-coder": "deepseek-ai/DeepSeek-Coder-V2-Instruct",
        "deepseek-r1": "deepseek-ai/DeepSeek-R1",
        # Yi 系列
        "yi": "01-ai/Yi-1.5-9B-Chat",
        # Phi 系列
        "phi": "microsoft/Phi-4-mini-instruct",
        "phi3": "microsoft/Phi-3-mini-4k-instruct",
        # GLM 系列
        "chatglm": "THUDM/glm-4-9b-chat",
        "glm4": "THUDM/glm-4-9b-chat",
        # MiniCPM
        "minicpm": "OpenBMB/MiniCPM-V-2_6",
    }

    # Ollama tag → ModelScope/HF 模型映射
    _OLLAMA_TAG_MAP: dict[str, dict] = {
        "qwen2.5:0.5b": {"modelscope": "Qwen/Qwen2.5-0.5B-Instruct", "hf": "Qwen/Qwen2.5-0.5B-Instruct", "format": "gguf"},
        "qwen2.5:1.5b": {"modelscope": "Qwen/Qwen2.5-1.5B-Instruct", "hf": "Qwen/Qwen2.5-1.5B-Instruct", "format": "gguf"},
        "qwen2.5:3b": {"modelscope": "Qwen/Qwen2.5-3B-Instruct", "hf": "Qwen/Qwen2.5-3B-Instruct", "format": "gguf"},
        "qwen2.5:7b": {"modelscope": "Qwen/Qwen2.5-7B-Instruct", "hf": "Qwen/Qwen2.5-7B-Instruct", "format": "gguf"},
        "qwen2.5:14b": {"modelscope": "Qwen/Qwen2.5-14B-Instruct", "hf": "Qwen/Qwen2.5-14B-Instruct", "format": "gguf"},
        "qwen2.5:32b": {"modelscope": "Qwen/Qwen2.5-32B-Instruct", "hf": "Qwen/Qwen2.5-32B-Instruct", "format": "gguf"},
        "qwen2.5:72b": {"modelscope": "Qwen/Qwen2.5-72B-Instruct", "hf": "Qwen/Qwen2.5-72B-Instruct", "format": "gguf"},
        "llama3.1:8b": {"modelscope": "LLM-Research/Meta-Llama-3.1-8B-Instruct-GGUF", "hf": "meta-llama/Llama-3.1-8B-Instruct", "format": "gguf"},
        "llama3.1:70b": {"modelscope": "LLM-Research/Meta-Llama-3.1-70B-Instruct-GGUF", "hf": "meta-llama/Llama-3.1-70B-Instruct", "format": "gguf"},
        "mistral:7b": {"modelscope": "mistralai/Mistral-7B-Instruct-v0.3-GGUF", "hf": "mistralai/Mistral-7B-Instruct-v0.3", "format": "gguf"},
        "gemma2:9b": {"modelscope": "google/gemma-2-9b-it-GGUF", "hf": "google/gemma-2-9b-it", "format": "gguf"},
        "deepseek-r1:1.5b": {"modelscope": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B-GGUF", "hf": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B", "format": "gguf"},
        "deepseek-r1:7b": {"modelscope": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B-GGUF", "hf": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "format": "gguf"},
        "deepseek-r1:8b": {"modelscope": "deepseek-ai/DeepSeek-R1-Distill-Llama-8B-GGUF", "hf": "deepseek-ai/DeepSeek-R1-Distill-Llama-8B", "format": "gguf"},
        "phi3:mini": {"modelscope": "LLM-Research/Phi-3-mini-4k-instruct-gguf", "hf": "microsoft/Phi-3-mini-4k-instruct", "format": "gguf"},
        "glm4:9b": {"modelscope": "THUDM/glm-4-9b-chat-GGUF", "hf": "THUDM/glm-4-9b-chat", "format": "gguf"},
    }

    def __init__(self):
        self._search_backends: list = []

    def register_search_backend(self, backend):
        """注册搜索后端 (必须实现 search_models 方法)"""
        self._search_backends.append(backend)

    def parse_model_name(self, raw_name: str) -> dict:
        """
        解析原始模型名，提取结构化信息

        支持格式:
        - "qwen2.5:0.5b"           → Ollama tag 格式
        - "Qwen/Qwen2.5-0.5B"      → HuggingFace 格式
        - "Qwen/Qwen2.5-0.5B-GGUF" → HF GGUF 格式
        - "qwen2.5-0.5b-instruct"  → 简化格式
        - "/path/to/model.gguf"     → 本地文件路径
        """
        raw_name = raw_name.strip()

        # 1) 本地路径 - 必须包含路径分隔符且后缀为已知模型格式
        KNOWN_FORMATS = {"gguf", "safetensors", "bin", "onnx", "pt", "pth", "ggml"}
        last_part = raw_name.split("/")[-1]
        has_known_ext = "." in last_part and last_part.rsplit(".", 1)[-1].lower() in KNOWN_FORMATS
        if "/" in raw_name and has_known_ext:
            return {
                "type": "local",
                "path": raw_name,
                "model_id": raw_name,
                "format": raw_name.rsplit(".", 1)[-1].lower(),
            }

        # 2) Ollama tag 格式: "name:tag"
        if ":" in raw_name and "/" not in raw_name:
            name, tag = raw_name.split(":", 1)
            return {
                "type": "ollama_tag",
                "name": name,
                "tag": tag,
                "model_id": raw_name,
            }

        # 3) HF/ModelScope 格式: "org/model-name"
        if "/" in raw_name:
            org, model = raw_name.split("/", 1)
            return {
                "type": "repo_id",
                "org": org,
                "model": model,
                "model_id": raw_name,
                "format": self._detect_format(model),
            }

        # 4) 简化名称: "qwen2.5-0.5b"
        return {
            "type": "alias",
            "name": raw_name,
            "model_id": raw_name,
        }

    def resolve(self, raw_name: str) -> tuple[Optional[ModelMatchResult], list[ModelMatchResult]]:
        """
        解析并搜索模型名

        返回:
        - (exact_match, similar_matches)
        - exact_match: 精确匹配结果 (可能为 None)
        - similar_matches: 相似推荐列表 (按 confidence 降序)
        """
        parsed = self.parse_model_name(raw_name)
        logger.info(f"解析模型名 '{raw_name}' → {parsed}")

        # === 本地文件 ===
        if parsed["type"] == "local":
            return ModelMatchResult(
                model_id=parsed["path"],
                display_name=parsed["path"].split("/")[-1],
                source=ModelSource.LOCAL,
                confidence=1.0,
                file_format=parsed.get("format", ""),
            ), []

        # === Ollama tag 精确映射 ===
        if parsed["type"] == "ollama_tag":
            ollama_key = f"{parsed['name']}:{parsed['tag']}".lower()
            # 精确查找
            if ollama_key in self._OLLAMA_TAG_MAP:
                info = self._OLLAMA_TAG_MAP[ollama_key]
                result = ModelMatchResult(
                    model_id=info["modelscope"],
                    display_name=raw_name,
                    source=ModelSource.MODELSCOPE,
                    confidence=1.0,
                    file_format=info.get("format", "gguf"),
                    tags=["gguf", "ollama-compatible"],
                )
                return result, self._find_similar_ollama(ollama_key)

            # 不带 tag 的模糊匹配
            name_only = parsed["name"]
            candidates = [k for k in self._OLLAMA_TAG_MAP if k.startswith(name_only + ":")]
            if candidates:
                results = []
                for c in candidates:
                    info = self._OLLAMA_TAG_MAP[c]
                    results.append(ModelMatchResult(
                        model_id=info["modelscope"],
                        display_name=c,
                        source=ModelSource.MODELSCOPE,
                        confidence=0.8,
                        file_format=info.get("format", "gguf"),
                    ))
                return None, results

        # === HF/ModelScope repo_id ===
        if parsed["type"] == "repo_id":
            result = ModelMatchResult(
                model_id=parsed["model_id"],
                display_name=parsed["model"],
                source=ModelSource.HUGGINGFACE,
                confidence=1.0,
                file_format=parsed.get("format", ""),
            )
            return result, []

        # === 别名 / 简化名称 ===
        if parsed["type"] == "alias":
            name_lower = parsed["name"].lower().strip()

            # 精确别名匹配
            if name_lower in self._ALIAS_MAP:
                canonical = self._ALIAS_MAP[name_lower]
                result = ModelMatchResult(
                    model_id=canonical,
                    display_name=parsed["name"],
                    source=ModelSource.HUGGINGFACE,
                    confidence=0.9,
                )
                return result, self._find_similar_alias(name_lower)

            # 模糊前缀匹配
            similar = self._find_similar_alias(name_lower)
            if similar:
                return None, similar

            # 尝试远程搜索
            remote_results = self._search_remotes(parsed["name"])
            if remote_results:
                return remote_results[0], remote_results[1:]

            return None, []

        return None, []

    def _detect_format(self, model_name: str) -> str:
        """从模型名推断格式"""
        model_lower = model_name.lower()
        if "gguf" in model_lower:
            return "gguf"
        if "gptq" in model_lower:
            return "gptq"
        if "awq" in model_lower:
            return "awq"
        if "safetensors" in model_lower:
            return "safetensors"
        return ""

    def _find_similar_ollama(self, ollama_key: str) -> list[ModelMatchResult]:
        """在 Ollama 映射表中找相似项"""
        name_part = ollama_key.split(":")[0]
        results = []
        for k, info in self._OLLAMA_TAG_MAP.items():
            if k != ollama_key and k.startswith(name_part + ":"):
                results.append(ModelMatchResult(
                    model_id=info["modelscope"],
                    display_name=k,
                    source=ModelSource.MODELSCOPE,
                    confidence=0.6,
                    file_format=info.get("format", "gguf"),
                    tags=["similar"],
                ))
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    def _find_similar_alias(self, name_lower: str) -> list[ModelMatchResult]:
        """在别名表中找相似项"""
        results = []
        for alias, canonical in self._ALIAS_MAP.items():
            # 简单前缀匹配
            if alias.startswith(name_lower[:3]) and alias != name_lower:
                results.append(ModelMatchResult(
                    model_id=canonical,
                    display_name=alias,
                    source=ModelSource.HUGGINGFACE,
                    confidence=0.5,
                ))
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:5]

    def _search_remotes(self, query: str) -> list[ModelMatchResult]:
        """调用远程搜索后端"""
        results = []
        for backend in self._search_backends:
            try:
                items = backend.search_models(query)
                results.extend(items)
            except Exception as e:
                logger.warning(f"搜索后端 {backend.__class__.__name__} 失败: {e}")
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:10]
