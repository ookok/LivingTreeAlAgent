# -*- coding: utf-8 -*-
"""
HuggingFace Tree 自动下载器
=========================

利用 huggingface_hub 实现"找最小量化版"：
- 自动扫描仓库下的所有 GGUF 文件
- 按大小排序，选择最优量化版本
- 支持断点续传
"""

import os
import hashlib
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass

try:
    from huggingface_hub import hf_hub_download, list_files_info
    HAS_HUGGINGFACE_HUB = True
except ImportError:
    HAS_HUGGINGFACE_HUB = False


# 量化等级优先级（越小越好）
QUANT_PRECEDENCE = {
    "q2_k": 1,
    "q3_k": 2,
    "q4_0": 3,
    "q4_k": 4,
    "q4_k_m": 5,  # 推荐
    "q5_0": 6,
    "q5_k": 7,
    "q5_k_m": 8,
    "q6_k": 9,
    "q8_0": 10,
}


@dataclass
class GGUFFileInfo:
    """GGUF 文件信息"""
    filename: str
    size: int
    download_url: str
    quant_type: str  # 如 q4_k_m
    repo_id: str


class HuggingFaceDownloader:
    """
    HuggingFace GGUF 仓库下载器

    功能：
    1. 扫描仓库所有 GGUF 文件
    2. 按量化类型和大小排序
    3. 自动选择最优版本
    4. 断点续传
    5. 支持国内镜像
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        hf_token: Optional[str] = None
    ):
        self.cache_dir = cache_dir or Path.home() / ".hermes-desktop" / "models"
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 设置国内镜像
        os.environ["HF_ENDPOINT"] = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")

        if not HAS_HUGGINGFACE_HUB:
            raise ImportError(
                "huggingface_hub 未安装，请运行: pip install huggingface-hub"
            )

    def list_gguf_files(self, repo_id: str) -> List[GGUFFileInfo]:
        """列出仓库中所有 GGUF 文件"""
        files = []
        for file_info in list_files_info(repo_id, token=self.hf_token):
            if file_info.path.endswith(".gguf"):
                quant_type = self._extract_quant_type(file_info.path)
                files.append(GGUFFileInfo(
                    filename=file_info.path,
                    size=file_info.size,
                    download_url=file_info.rfilename,
                    quant_type=quant_type,
                    repo_id=repo_id,
                ))
        return files

    def _extract_quant_type(self, filename: str) -> str:
        """从文件名提取量化类型"""
        filename_lower = filename.lower()
        for quant in QUANT_PRECEDENCE.keys():
            if quant in filename_lower:
                return quant
        return "unknown"

    def find_best_gguf(
        self,
        repo_id: str,
        prefer_quant: Optional[str] = None
    ) -> Optional[GGUFFileInfo]:
        """
        找到最优 GGUF 文件

        Args:
            repo_id: HuggingFace 仓库 ID
            prefer_quant: 偏好量化类型（如 q4_k_m）

        Returns:
            最优 GGUF 文件信息
        """
        files = self.list_gguf_files(repo_id)
        if not files:
            return None

        # 如果指定了偏好量化，优先选择
        if prefer_quant:
            preferred = [f for f in files if f.quant_type == prefer_quant]
            if preferred:
                # 在同类型中选择最小的
                return min(preferred, key=lambda x: x.size)

        # 否则按量化优先级和大小综合选择
        def sort_key(f: GGUFFileInfo):
            quant_score = QUANT_PRECEDENCE.get(f.quant_type, 999)
            return (quant_score, f.size)

        return min(files, key=sort_key)

    def download(
        self,
        repo_id: str,
        filename: Optional[str] = None,
        prefer_quant: str = "q4_k_m",
        force: bool = False
    ) -> Optional[Path]:
        """
        下载 GGUF 文件

        Args:
            repo_id: HuggingFace 仓库 ID
            filename: 指定文件名，不指定则自动选择
            prefer_quant: 偏好量化类型
            force: 强制重新下载

        Returns:
            下载后的本地文件路径
        """
        # 找到最优文件
        if filename:
            file_info = GGUFFileInfo(
                filename=filename,
                size=0,
                download_url=filename,
                quant_type=self._extract_quant_type(filename),
                repo_id=repo_id,
            )
        else:
            file_info = self.find_best_gguf(repo_id, prefer_quant)
            if not file_info:
                print(f"未找到 GGUF 文件: {repo_id}")
                return None

        # 本地路径
        local_path = self.cache_dir / file_info.filename

        # 检查是否已存在
        if local_path.exists() and not force:
            print(f"文件已存在: {local_path}")
            return local_path

        # 下载
        try:
            print(f"正在下载: {repo_id}/{file_info.filename}")
            downloaded = hf_hub_download(
                repo_id=repo_id,
                filename=file_info.filename,
                local_dir=self.cache_dir,
                token=self.hf_token,
            )
            return Path(downloaded)
        except Exception as e:
            print(f"下载失败: {e}")
            return None

    def get_model_info(self, repo_id: str) -> Dict:
        """获取模型信息"""
        best = self.find_best_gguf(repo_id)
        if best:
            return {
                "repo_id": repo_id,
                "best_file": best.filename,
                "quant_type": best.quant_type,
                "size_mb": best.size / (1024 * 1024),
            }
        return {}


# ==================== 快捷函数 ====================

def find_smallest_gguf(repo_id: str) -> Optional[str]:
    """
    找到最小量化版 GGUF 的下载 URL

    用法：
    >>> url = find_smallest_gguf("second-state/SmolLM2-135M-Instruct-GGUF")
    >>> print(url)
    'https://huggingface.co/second-state/SmolLM2-135M-Instruct-GGUF/resolve/main/smollm2-135m-instruct-q4_k_m.gguf'
    """
    if not HAS_HUGGINGFACE_HUB:
        return None

    downloader = HuggingFaceDownloader()
    best = downloader.find_best_gguf(repo_id)
    return best.download_url if best else None


def download_smolllm2(
    cache_dir: Optional[Path] = None,
    prefer_quant: str = "q4_k_m"
) -> Optional[Path]:
    """
    下载 SmolLM2-135M GGUF 模型

    用法：
    >>> path = download_smolllm2()
    >>> print(path)
    PosixPath('/root/.hermes-desktop/models/smollm2-135m-instruct-q4_k_m.gguf')
    """
    downloader = HuggingFaceDownloader(cache_dir=cache_dir)
    return downloader.download(
        repo_id="second-state/SmolLM2-135M-Instruct-GGUF",
        prefer_quant=prefer_quant
    )


# ==================== 工具清单定义 ====================

SMOLLLM2_MANIFEST = {
    "id": "smollm2-135m",
    "name": "SmolLM2-135M GGUF",
    "desc": "轻量意图识别与路由模型 (~60MB)",
    "quant_type": "q4_k_m",
    "platforms": {
        "any": {
            "repo_id": "second-state/SmolLM2-135M-Instruct-GGUF",
            "filename": "smollm2-135m-instruct-q4_k_m.gguf",
            "size_mb": 60,
            "hf_tree": True,  # 标志位：支持自动找量化变体
        }
    }
}
