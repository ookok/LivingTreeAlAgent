# -*- coding: utf-8 -*-
"""
统一模型管理器 (Model Hub Manager)

顶层入口, 整合 Resolver + Sources + Loader + Registry:
1. 输入模型名 → 解析 → 搜索 → 推荐
2. 选择模型 → 下载 (多源自动降级)
3. 下载完成 → 自动注册
4. 加载模型 → 自动选择后端
from __future__ import annotations
"""


import os
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .resolver import ModelResolver, ModelMatchResult, ModelSource
from .sources import (
    ModelScopeSource, HuggingFaceSource, GithubSource,
    DownloadConfig, DownloadProgress,
)
from .loader import ModelLoader, LoadConfig, LoadResult, LoadBackend
from .registry import ModelRegistry, ModelRecord

logger = logging.getLogger(__name__)


@dataclass
class HubConfig:
    """ModelHub 全局配置"""
    download_dir: str = ""
    hf_mirror: str = "https://hf-mirror.com"
    prefer_modelscope: bool = True
    ollama_host: str = "http://localhost:11434"
    vllm_host: str = "http://localhost:8000"
    auto_register: bool = True
    registry_dir: str = ""


class ModelHubManager:
    """
    统一模型管理器

    用法示例:
        hub = ModelHubManager()
        match, similar = hub.resolve("qwen2.5:0.5b")
        progress = hub.download("Qwen/Qwen2.5-0.5B-Instruct")
        result = hub.load("qwen2.5:0.5b")
        text = hub.generate("你好")
    """

    def __init__(self, config: Optional[HubConfig] = None):
        self._config = config or HubConfig()

        # 初始化组件
        self.resolver = ModelResolver()
        self.loader = ModelLoader()
        self.registry = ModelRegistry(
            registry_dir=self._config.registry_dir or None
        )

        # 初始化下载源
        self._modelscope = ModelScopeSource()
        self._huggingface = HuggingFaceSource()
        self._github = GithubSource()

        if self._config.hf_mirror:
            self._huggingface.set_mirror(self._config.hf_mirror)

        # 注册搜索后端到 resolver
        self.resolver.register_search_backend(self._modelscope)
        self.resolver.register_search_backend(self._huggingface)

        # 加载本地注册表
        self.registry.load()

        # 当前状态
        self._current_load_result: Optional[LoadResult] = None

    # ==================== 搜索与解析 ====================

    def resolve(self, model_name: str) -> tuple:
        """
        解析模型名, 搜索匹配

        Returns:
            (exact_match: Optional[ModelMatchResult], similar: List[ModelMatchResult])
        """
        exact, similar = self.resolver.resolve(model_name)

        # 补充本地注册表信息
        if exact:
            local = self.registry.get(exact.model_id)
            if local:
                exact.file_size = local.file_size or exact.file_size

        return exact, similar

    def search(self, query: str, limit: int = 10) -> List[dict]:
        """搜索模型"""
        all_results = []

        # ModelScope
        if self._config.prefer_modelscope:
            ms_results = self._modelscope.search_models(query, limit)
            for r in ms_results:
                all_results.append(ModelMatchResult(
                    model_id=r["model_id"],
                    display_name=r.get("display_name", r["model_id"]),
                    source=ModelSource.MODELSCOPE,
                    confidence=0.7,
                    file_size=r.get("file_size", 0),
                    tags=r.get("tags", []),
                    description=r.get("description", ""),
                ))

        # HuggingFace
        hf_results = self._huggingface.search_models(query, limit)
        for r in hf_results:
            all_results.append(ModelMatchResult(
                model_id=r["model_id"],
                display_name=r.get("display_name", r["model_id"]),
                source=ModelSource.HUGGINGFACE,
                confidence=0.7,
                tags=r.get("tags", []),
                description=r.get("description", ""),
            ))

        all_results.sort(key=lambda x: x.confidence, reverse=True)
        return [r.to_dict() for r in all_results[:limit * 2]]

    # ==================== 下载 ====================

    def download(
        self,
        model_name: str,
        save_dir: Optional[str] = None,
        gguf_only: bool = False,
        source: str = "auto",
        hf_mirror: str = "https://hf-mirror.com",
    ) -> dict:
        """
        下载模型

        Returns:
            dict with keys: success, model_id, save_path, source, format, files, similar, error
        """
        # Step 1: 解析模型名
        exact_match, similar = self.resolver.resolve(model_name)

        if exact_match is None and similar:
            return {
                "success": False, "model_id": model_name,
                "save_path": "", "source": "", "format": "",
                "files": [], "similar": [s.to_dict() for s in similar],
                "error": f"未找到精确匹配 '{model_name}'，以下是相似模型:",
            }

        if exact_match is None:
            return {
                "success": False, "model_id": model_name,
                "save_path": "", "source": "", "format": "",
                "files": [], "similar": [],
                "error": f"未找到模型 '{model_name}'，且无相似推荐",
            }

        target_id = exact_match.model_id

        # Step 2: 检查是否已下载
        existing = self.registry.get(target_id)
        if existing and Path(existing.local_path).exists():
            logger.info(f"模型已存在: {target_id} → {existing.local_path}")
            return {
                "success": True, "model_id": target_id,
                "save_path": existing.local_path,
                "source": existing.source,
                "format": existing.file_format,
                "files": [existing.local_path],
                "similar": [s.to_dict() for s in similar],
                "error": None, "cached": True,
            }

        # Step 3: 构建下载配置
        download_config = DownloadConfig(
            output_dir=save_dir or self._config.download_dir,
            gguf_only=gguf_only,
            hf_mirror=hf_mirror,
        )

        # Step 4: 选择下载源
        sources_order = self._get_source_order(source, exact_match.source)
        last_error = ""

        for src in sources_order:
            progress = src.download(target_id, download_config)
            if progress.status == "completed":
                # 收集文件
                files = []
                out_path = progress.output_path
                if out_path and Path(out_path).exists():
                    if Path(out_path).is_file():
                        files.append(out_path)
                    elif Path(out_path).is_dir():
                        files = [str(f) for f in Path(out_path).rglob("*") if f.is_file()]

                # 自动注册
                if self._config.auto_register:
                    self._auto_register(progress, src.name(), exact_match, model_name, files)

                return {
                    "success": True, "model_id": target_id,
                    "save_path": out_path or "",
                    "source": src.name(),
                    "format": exact_match.file_format,
                    "files": files,
                    "similar": [s.to_dict() for s in similar],
                    "error": None,
                }
            last_error = progress.error_message
            logger.warning(f"{src.name()} 下载失败: {last_error}")

        return {
            "success": False, "model_id": target_id,
            "save_path": "", "source": "", "format": "",
            "files": [], "similar": [s.to_dict() for s in similar],
            "error": f"所有源均下载失败。最后错误: {last_error}",
        }

    def _get_source_order(self, source: str, match_source: ModelSource) -> list:
        """获取源优先级"""
        all_sources = [
            (ModelSource.MODELSCOPE, self._modelscope),
            (ModelSource.HUGGINGFACE, self._huggingface),
            (ModelSource.GITHUB, self._github),
        ]

        if source == "modelscope":
            order = [self._modelscope, self._huggingface, self._github]
        elif source == "huggingface":
            order = [self._huggingface, self._modelscope, self._github]
        elif source == "github":
            order = [self._github, self._huggingface, self._modelscope]
        else:
            # 按匹配来源优先
            matched_src = next((s for src_type, s in all_sources if src_type == match_source), None)
            order = []
            if matched_src:
                order.append(matched_src)
            order.extend([self._modelscope, self._huggingface, self._github])
            # 去重
            seen = set()
            unique_order = []
            for s in order:
                if id(s) not in seen:
                    seen.add(id(s))
                    unique_order.append(s)
            order = unique_order

        if self._config.prefer_modelscope:
            # 确保 modelscope 在前面
            if self._modelscope in order:
                order.remove(self._modelscope)
                order.insert(0, self._modelscope)

        return order

    def _auto_register(self, progress: DownloadProgress, source_name: str,
                       match: ModelMatchResult, raw_name: str, files: List[str]):
        """下载成功后自动注册"""
        if not progress.output_path:
            return

        gguf_path = ""
        if os.path.isdir(progress.output_path):
            for f in os.listdir(progress.output_path):
                if f.lower().endswith(".gguf"):
                    gguf_path = os.path.join(progress.output_path, f)
                    break

        record = ModelRecord(
            model_id=match.model_id,
            display_name=match.display_name,
            local_path=progress.output_path,
            source=source_name,
            file_format=match.file_format or ("gguf" if gguf_path else ""),
            file_size=progress.total_bytes,
            downloaded_at=datetime.now().isoformat(),
            gguf_path=gguf_path,
            tags=match.tags + ["downloaded"],
        )
        self.registry.register(record)

    # ==================== 加载 ====================

    def load(
        self,
        model_name: str = "",
        model_path: str = "",
        backend: str = "auto",
        context_size: int = 4096,
        gguf_file: str = "",
        **kwargs,
    ) -> LoadResult:
        """加载模型"""
        # 从注册表查找路径
        effective_name = model_name or model_path
        if effective_name and not model_path:
            record = self.registry.find_gguf_for_ollama(effective_name)
            if record and record.gguf_path:
                model_path = record.gguf_path
            elif record:
                model_path = record.local_path

        load_config = LoadConfig(
            backend=backend,
            model_path=model_path,
            model_name=model_name,
            gguf_file=gguf_file,
            ollama_host=self._config.ollama_host,
            vllm_host=self._config.vllm_host,
            context_size=context_size,
            extra_kwargs=kwargs,
        )

        result = self.loader.load(load_config)
        self._current_load_result = result
        return result

    def generate(self, prompt: str, **kwargs) -> str:
        """使用当前加载的模型生成文本"""
        return self.loader.generate(prompt, **kwargs)

    def unload(self):
        """卸载当前模型"""
        self.loader.unload()
        self._current_load_result = None

    # ==================== 查询 ====================

    def get_available_backends(self) -> List[dict]:
        """列出所有可用的加载后端"""
        return self.loader.get_available_backends()

    def list_backends(self) -> List[dict]:
        """别名"""
        return self.get_available_backends()

    def get_local_models(self, query: str = "") -> List[ModelRecord]:
        """查询本地已注册模型"""
        return self.registry.search(query)

    def list_models(self, source: str = "", fmt: str = "") -> List[ModelRecord]:
        """列出已下载的模型"""
        return self.registry.search(source=source, fmt=fmt)

    def get_model(self, model_id: str) -> Optional[ModelRecord]:
        """查询模型信息"""
        return self.registry.get(model_id)

    def get_registry_summary(self) -> dict:
        """获取本地模型注册表摘要"""
        return self.registry.get_summary()

    def scan_local_models(self, extra_dirs: Optional[List[str]] = None) -> int:
        """扫描本地模型目录"""
        return self.registry.scan_local_models(extra_dirs)

    def list_sources(self) -> List[dict]:
        """列出可用的下载源"""
        sources = [
            ("modelscope", self._modelscope),
            ("huggingface", self._huggingface),
            ("github", self._github),
        ]
        return [
            {
                "name": name,
                "class": src.__class__.__name__,
                "available": src.is_available(),
            }
            for name, src in sources
        ]
