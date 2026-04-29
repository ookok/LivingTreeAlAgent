# -*- coding: utf-8 -*-
"""
多源模型下载封装
支持 ModelScope / HuggingFace Hub / GitHub
from __future__ import annotations
"""


import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DownloadProgress:
    """下载进度"""
    model_id: str
    source: str
    total_bytes: int = 0
    downloaded_bytes: int = 0
    speed_bytes_per_sec: float = 0.0
    status: str = "pending"  # pending, downloading, completed, failed, cancelled
    error_message: str = ""
    output_path: str = ""

    @property
    def progress_pct(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, (self.downloaded_bytes / self.total_bytes) * 100)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "source": self.source,
            "total_bytes": self.total_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "speed_bytes_per_sec": self.speed_bytes_per_sec,
            "status": self.status,
            "error_message": self.error_message,
            "output_path": self.output_path,
            "progress_pct": round(self.progress_pct, 1),
        }


@dataclass
class DownloadConfig:
    """下载配置"""
    output_dir: str = ""
    overwrite: bool = False
    gguf_only: bool = False
    max_workers: int = 4
    use_modelscope_mirror: bool = True
    hf_mirror: str = "https://hf-mirror.com"
    proxy: str = ""
    progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=lambda: [
        "*.onnx", "*.ot", "*.msgpack", "original/*", "logs/*"
    ])


class ModelSourceBase(ABC):
    """模型源基类"""

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def search_models(self, query: str, limit: int = 10) -> list[dict]: ...

    @abstractmethod
    def download(self, model_id: str, config: DownloadConfig) -> DownloadProgress: ...

    def check_model_exists(self, model_id: str) -> bool:
        """检查模型是否存在 (默认实现)"""
        return True


class ModelScopeSource(ModelSourceBase):
    """
    阿里魔塔社区 (ModelScope) 模型源
    pip install modelscope
    """

    def __init__(self):
        self._snapshot_download = None

    def name(self) -> str:
        return "modelscope"

    def is_available(self) -> bool:
        try:
            from modelscope import snapshot_download
            self._snapshot_download = snapshot_download
            return True
        except ImportError:
            return False

    def search_models(self, query: str, limit: int = 10) -> list[dict]:
        try:
            from modelscope.hub.api import HubApi
            api = HubApi()
            results = api.list_models(search=query, limit=limit)
            return [{
                "model_id": item.get("model_id", item.get("name", "")),
                "display_name": item.get("name", ""),
                "description": item.get("description", ""),
                "file_size": item.get("file_size", 0),
                "tags": item.get("tags", []),
                "source": "modelscope",
            } for item in (results or [])]
        except ImportError:
            logger.warning("ModelScope SDK 未安装, 无法搜索")
            return []
        except Exception as e:
            logger.error(f"ModelScope 搜索失败: {e}")
            return []

    def download(self, model_id: str, config: DownloadConfig) -> DownloadProgress:
        progress = DownloadProgress(
            model_id=model_id, source=self.name(), status="downloading",
            output_path=config.output_dir or str(Path.home() / ".cache" / "modelscope" / "hub" / model_id.replace("/", "--")),
        )
        try:
            if not self.is_available():
                progress.status = "failed"
                progress.error_message = "ModelScope SDK 未安装: pip install modelscope"
                return progress

            kwargs = {
                "model_id": model_id,
                "cache_dir": config.output_dir or str(Path.home() / ".cache" / "modelscope" / "hub"),
            }
            if config.gguf_only:
                kwargs["allow_patterns"] = ["*.gguf", "*.GGUF"]
            elif config.include_patterns:
                kwargs["allow_patterns"] = config.include_patterns
            if config.exclude_patterns:
                kwargs["ignore_patterns"] = config.exclude_patterns

            progress.output_path = self._snapshot_download(**kwargs)
            progress.status = "completed"

            total_size = sum(f.stat().st_size for f in Path(progress.output_path).rglob("*") if f.is_file())
            progress.total_bytes = total_size
            progress.downloaded_bytes = total_size

            if config.progress_callback:
                config.progress_callback(progress)
        except Exception as e:
            progress.status = "failed"
            progress.error_message = str(e)
            logger.error(f"ModelScope 下载失败 [{model_id}]: {e}")

        return progress


class HuggingFaceSource(ModelSourceBase):
    """
    HuggingFace Hub 模型源
    pip install huggingface_hub
    支持镜像站 hf-mirror.com
    """

    def __init__(self):
        self._mirror: str = ""

    def name(self) -> str:
        return "huggingface"

    def is_available(self) -> bool:
        try:
            import huggingface_hub
            return True
        except ImportError:
            return False

    def set_mirror(self, mirror_url: str):
        self._mirror = mirror_url
        os.environ.setdefault("HF_ENDPOINT", mirror_url)
        logger.info(f"HuggingFace 镜像已设置: {mirror_url}")

    def search_models(self, query: str, limit: int = 10) -> list[dict]:
        try:
            from huggingface_hub import HfApi
            api = HfApi()
            results = list(api.list_models(search=query, limit=limit, sort="downloads"))
            return [{
                "model_id": m.id,
                "display_name": m.id.split("/")[-1] if "/" in m.id else m.id,
                "description": getattr(m, "card_data", None) and m.card_data.get("description", "") or "",
                "file_size": 0,
                "tags": getattr(m, "tags", []) or [],
                "downloads": getattr(m, "downloads", 0) or 0,
                "source": "huggingface",
            } for m in results]
        except ImportError:
            logger.warning("huggingface_hub 未安装, 无法搜索")
            return []
        except Exception as e:
            logger.error(f"HuggingFace 搜索失败: {e}")
            return []

    def download(self, model_id: str, config: DownloadConfig) -> DownloadProgress:
        progress = DownloadProgress(
            model_id=model_id, source=self.name(), status="downloading",
            output_path=config.output_dir or str(Path.home() / ".cache" / "huggingface" / "hub"),
        )
        try:
            if not self.is_available():
                progress.status = "failed"
                progress.error_message = "huggingface_hub 未安装: pip install huggingface_hub"
                return progress

            from huggingface_hub import snapshot_download as hf_snapshot, list_repo_files

            # 如果只需要 GGUF，先检查仓库文件
            if config.gguf_only:
                try:
                    repo_files = list_repo_files(model_id)
                    gguf_files = [f for f in repo_files if f.lower().endswith(".gguf")]
                    if not gguf_files:
                        # 尝试 -GGUF 后缀仓库
                        gguf_repo = model_id + "-GGUF"
                        try:
                            gguf_repo_files = list_repo_files(gguf_repo)
                            gguf_files = [f for f in gguf_repo_files if f.lower().endswith(".gguf")]
                            if gguf_files:
                                model_id = gguf_repo
                        except Exception:
                            pass
                except Exception:
                    pass

            kwargs = {
                "repo_id": model_id,
                "cache_dir": config.output_dir or str(Path.home() / ".cache" / "huggingface" / "hub"),
            }
            if config.gguf_only:
                kwargs["allow_patterns"] = ["*.gguf", "*.GGUF"]
            elif config.include_patterns:
                kwargs["allow_patterns"] = config.include_patterns
            if config.exclude_patterns:
                kwargs["ignore_patterns"] = config.exclude_patterns

            progress.output_path = hf_snapshot(**kwargs)
            progress.status = "completed"

            total_size = sum(f.stat().st_size for f in Path(progress.output_path).rglob("*") if f.is_file())
            progress.total_bytes = total_size
            progress.downloaded_bytes = total_size

            if config.progress_callback:
                config.progress_callback(progress)
        except Exception as e:
            progress.status = "failed"
            progress.error_message = str(e)
            logger.error(f"HuggingFace 下载失败 [{model_id}]: {e}")

        return progress


class GithubSource(ModelSourceBase):
    """
    GitHub Release 模型源
    """

    def name(self) -> str:
        return "github"

    def is_available(self) -> bool:
        try:
            import urllib.request
            return True
        except ImportError:
            return False

    def search_models(self, query: str, limit: int = 10) -> list[dict]:
        try:
            import urllib.request
            import json
            url = f"https://api.github.com/search/repositories?q={query}+topic:llm&sort=stars&per_page={limit}"
            req = urllib.request.Request(url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "LivingTreeAI-ModelHub"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return [{
                "model_id": item["full_name"],
                "display_name": item["name"],
                "description": item.get("description", ""),
                "file_size": 0,
                "tags": [t["name"] for t in item.get("topics", [])],
                "source": "github",
            } for item in data.get("items", [])]
        except Exception as e:
            logger.error(f"GitHub 搜索失败: {e}")
            return []

    def download(self, model_id: str, config: DownloadConfig) -> DownloadProgress:
        progress = DownloadProgress(model_id=model_id, source=self.name(), status="downloading")
        try:
            import urllib.request
            import json

            api_url = f"https://api.github.com/repos/{model_id}/releases/latest"
            req = urllib.request.Request(api_url, headers={"User-Agent": "LivingTreeAI"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                release = json.loads(resp.read())

            output_dir = config.output_dir or str(Path.home() / ".cache" / "model_hub" / "github" / model_id.replace("/", "--"))
            os.makedirs(output_dir, exist_ok=True)

            assets = release.get("assets", [])
            if config.gguf_only:
                assets = [a for a in assets if a["name"].endswith(".gguf")]

            for asset in assets:
                file_path = os.path.join(output_dir, asset["name"])
                if os.path.exists(file_path) and not config.overwrite:
                    logger.info(f"文件已存在, 跳过: {file_path}")
                    continue
                logger.info(f"正在下载: {asset['name']} ({asset['size'] / 1024 / 1024:.1f} MB)")
                urllib.request.urlretrieve(asset["browser_download_url"], file_path)
                progress.total_bytes += asset["size"]
                progress.downloaded_bytes += asset["size"]

            progress.output_path = output_dir
            progress.status = "completed"
        except Exception as e:
            progress.status = "failed"
            progress.error_message = str(e)
            logger.error(f"GitHub 下载失败 [{model_id}]: {e}")

        return progress
