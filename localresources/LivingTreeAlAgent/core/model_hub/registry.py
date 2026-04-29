# -*- coding: utf-8 -*-
"""
模型本地注册表 (Model Registry)
跟踪已下载的模型，提供快速查询
"""

from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_PATH = Path.home() / ".cache" / "model-hub" / "registry.json"


@dataclass
class ModelRecord:
    """已注册模型记录"""
    model_id: str
    display_name: str
    source: str
    local_path: str
    file_format: str
    file_size: int
    downloaded_at: str = ""
    last_used_at: str = ""
    tags: List[str] = field(default_factory=list)
    description: str = ""
    ollama_name: str = ""
    gguf_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ModelRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ModelRegistry:
    """模型注册表"""

    def __init__(self, registry_path=None, registry_dir=None):
        if registry_dir:
            self._path = Path(registry_dir) / "registry.json"
        elif registry_path:
            self._path = Path(registry_path)
        else:
            self._path = DEFAULT_REGISTRY_PATH
        self._records: dict = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._records = {k: ModelRecord.from_dict(v) for k, v in data.items()}
                logger.info(f"[Registry] loaded {len(self._records)} models")
            except Exception as e:
                logger.warning(f"[Registry] load failed: {e}")
                self._records = {}
        else:
            self._records = {}
            self._path.parent.mkdir(parents=True, exist_ok=True)

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump({k: v.to_dict() for k, v in self._records.items()},
                      f, ensure_ascii=False, indent=2)

    def load(self):
        """Public load (re-load from file)"""
        self._load()

    def save(self):
        """Public save"""
        self._save()

    def register(self, record: ModelRecord) -> None:
        self._records[record.model_id] = record
        self._save()
        logger.info(f"[Registry] registered: {record.model_id} -> {record.local_path}")

    def unregister(self, model_id: str) -> bool:
        if model_id in self._records:
            del self._records[model_id]
            self._save()
            return True
        return False

    def get(self, model_id: str) -> Optional[ModelRecord]:
        return self._records.get(model_id)

    def list_all(self, source: str = "", format: str = "", tag: str = "") -> List[ModelRecord]:
        results = list(self._records.values())
        if source:
            results = [r for r in results if r.source == source]
        if format:
            results = [r for r in results if r.file_format == format]
        if tag:
            results = [r for r in results if tag in r.tags]
        return results

    def search(self, query: str = "", source: str = "", fmt: str = "") -> List[ModelRecord]:
        """搜索模型"""
        results = list(self._records.values())
        if source:
            results = [r for r in results if r.source == source]
        if fmt:
            results = [r for r in results if r.file_format == fmt]
        if query:
            q = query.lower()
            results = [r for r in results
                       if q in r.model_id.lower() or q in r.display_name.lower()
                       or any(q in t.lower() for t in r.tags)]
        return results

    def find_gguf_for_ollama(self, model_id: str) -> Optional[ModelRecord]:
        """查找可用于 Ollama 的 GGUF 模型"""
        record = self._records.get(model_id)
        if record:
            # 检查 gguf_path 或 local_path
            gguf = record.gguf_path or ""
            if not gguf and record.local_path:
                if record.local_path.lower().endswith(".gguf"):
                    gguf = record.local_path
            if gguf and os.path.exists(gguf):
                return record
        # 模糊匹配
        mid_lower = model_id.lower().replace("-", "").replace("_", "")
        for r in self._records.values():
            rid = r.model_id.lower().replace("-", "").replace("_", "")
            if mid_lower in rid or rid in mid_lower:
                gguf = r.gguf_path or r.local_path
                if gguf and os.path.exists(gguf) and gguf.lower().endswith(".gguf"):
                    return r
        return None

    def list_gguf(self) -> List[ModelRecord]:
        """列出所有 GGUF 模型"""
        return [r for r in self._records.values() if r.file_format == "gguf"]

    def touch(self, model_id: str) -> None:
        if model_id in self._records:
            self._records[model_id].last_used_at = datetime.now().isoformat()
            self._save()

    def find_by_path(self, path: str) -> Optional[ModelRecord]:
        path = str(path).replace("\\", "/")
        for r in self._records.values():
            if r.local_path.replace("\\", "/") == path:
                return r
            if path in r.local_path or r.local_path in path:
                return r
        return None

    def get_summary(self) -> dict:
        """获取注册表摘要"""
        total = len(self._records)
        by_source = {}
        by_format = {}
        total_size = 0
        for r in self._records.values():
            by_source[r.source] = by_source.get(r.source, 0) + 1
            by_format[r.file_format] = by_format.get(r.file_format, 0) + 1
            total_size += r.file_size
        return {
            "total_models": total,
            "by_source": by_source,
            "by_format": by_format,
            "total_size_bytes": total_size,
            "total_size_human": self._format_size(total_size),
        }

    def scan_local_models(self, extra_dirs=None) -> int:
        """扫描本地模型目录"""
        scan_dirs = [
            str(Path.home() / ".cache" / "modelscope" / "hub"),
            str(Path.home() / ".cache" / "huggingface" / "hub"),
            str(Path.home() / ".cache" / "model_hub"),
        ]
        if extra_dirs:
            scan_dirs.extend(extra_dirs)
        new_count = 0
        for d in scan_dirs:
            if not os.path.isdir(d):
                continue
            new_count += self._scan_dir(d)
        if new_count > 0:
            self._save()
        return new_count

    def _scan_dir(self, base_dir: str) -> int:
        new_count = 0
        try:
            for entry in os.listdir(base_dir):
                entry_path = os.path.join(base_dir, entry)
                if not os.path.isdir(entry_path) or entry.startswith("."):
                    continue
                model_files = self._find_model_files(entry_path)
                if not model_files:
                    for sub in os.listdir(entry_path):
                        sub_path = os.path.join(entry_path, sub)
                        if os.path.isdir(sub_path):
                            mf = self._find_model_files(sub_path)
                            if mf:
                                model_files = mf
                                entry_path = sub_path
                                break
                if model_files and entry not in self._records:
                    primary_fmt = model_files[0][1]
                    gguf = ""
                    size = 0
                    for fp, fmt in model_files:
                        size += os.path.getsize(fp) if os.path.exists(fp) else 0
                        if fmt == "gguf" and not gguf:
                            gguf = fp
                    self._records[entry] = ModelRecord(
                        model_id=entry,
                        display_name=entry,
                        local_path=entry_path,
                        source=self._detect_source(base_dir),
                        file_format=primary_fmt,
                        file_size=size,
                        downloaded_at=datetime.now().isoformat(),
                        gguf_path=gguf,
                    )
                    new_count += 1
        except PermissionError:
            pass
        return new_count

    @staticmethod
    def _find_model_files(directory: str) -> list:
        exts = {".gguf": "gguf", ".safetensors": "safetensors", ".bin": "bin"}
        found = []
        try:
            for f in os.listdir(directory):
                ext = os.path.splitext(f)[1].lower()
                if ext in exts:
                    found.append((os.path.join(directory, f), exts[ext]))
        except PermissionError:
            pass
        return found

    @staticmethod
    def _detect_source(base_dir: str) -> str:
        d = base_dir.lower()
        if "modelscope" in d:
            return "modelscope"
        if "huggingface" in d:
            return "huggingface"
        return "local"

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}PB"
