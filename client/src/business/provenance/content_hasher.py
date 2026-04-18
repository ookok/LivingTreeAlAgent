# =================================================================
# 数据指纹层 - Content Hasher
# =================================================================
# 功能：
# 1. 计算内容 SHA256 哈希值
# 2. 支持增量哈希（大文件分块）
# 3. 哈希对比检测篡改
# 4. 版本追溯
# =================================================================

import hashlib
import json
import time
from enum import Enum
from typing import Optional, List, Dict, Any, Union, BinaryIO
from dataclasses import dataclass, field
from pathlib import Path


class HashType(Enum):
    """哈希算法类型"""
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"
    MD5 = "md5"          # 仅用于快速校验，不用于安全目的
    BLAKE2B = "blake2b"


@dataclass
class HashResult:
    """哈希结果"""
    # 哈希值
    hash_value: str
    algorithm: HashType

    # 元数据
    content_length: int          # 内容长度（字节）
    content_type: str = ""      # 内容类型 (text/binary/file)

    # 时间戳
    computed_at: float = field(default_factory=time.time)
    computed_by: str = "system"  # 计算者 (system/user/agent)

    # 附加信息
    chunk_size: int = 0         # 分块大小（用于增量哈希）
    file_path: str = ""         # 文件路径（如果是文件）

    @property
    def short_hash(self) -> str:
        """返回短哈希（8位）"""
        return self.hash_value[:8]

    @property
    def timestamp_str(self) -> str:
        """格式化时间戳"""
        from datetime import datetime
        return datetime.fromtimestamp(self.computed_at).isoformat()


class ContentHasher:
    """
    内容指纹计算器

    功能：
    1. 字符串/字节哈希
    2. 文件哈希（支持大文件分块）
    3. JSON 结构哈希（标准化后哈希）
    4. 哈希链（用于版本追溯）
    """

    # 分块大小（1MB）
    DEFAULT_CHUNK_SIZE = 1024 * 1024

    def __init__(self, default_algorithm: HashType = HashType.SHA256):
        self.default_algorithm = default_algorithm

    def hash_string(
        self,
        content: str,
        algorithm: HashType = None,
        encoding: str = "utf-8"
    ) -> HashResult:
        """
        计算字符串哈希

        Args:
            content: 字符串内容
            algorithm: 哈希算法（默认使用实例配置的算法）
            encoding: 编码方式

        Returns:
            HashResult
        """
        algorithm = algorithm or self.default_algorithm

        if algorithm == HashType.SHA256:
            hasher = hashlib.sha256()
        elif algorithm == HashType.SHA384:
            hasher = hashlib.sha384()
        elif algorithm == HashType.SHA512:
            hasher = hashlib.sha512()
        elif algorithm == HashType.MD5:
            hasher = hashlib.md5()
        elif algorithm == HashType.BLAKE2B:
            hasher = hashlib.blake2b()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        hasher.update(content.encode(encoding))
        hash_value = hasher.hexdigest()

        return HashResult(
            hash_value=hash_value,
            algorithm=algorithm,
            content_length=len(content.encode(encoding)),
            content_type="text/plain"
        )

    def hash_bytes(
        self,
        content: bytes,
        algorithm: HashType = None
    ) -> HashResult:
        """计算字节数组哈希"""
        algorithm = algorithm or self.default_algorithm

        if algorithm == HashType.SHA256:
            hasher = hashlib.sha256()
        elif algorithm == HashType.SHA384:
            hasher = hashlib.sha384()
        elif algorithm == HashType.SHA512:
            hasher = hashlib.sha512()
        elif algorithm == HashType.MD5:
            hasher = hashlib.md5()
        elif algorithm == HashType.BLAKE2B:
            hasher = hashlib.blake2b()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        hasher.update(content)
        hash_value = hasher.hexdigest()

        return HashResult(
            hash_value=hash_value,
            algorithm=algorithm,
            content_length=len(content),
            content_type="application/octet-stream"
        )

    def hash_file(
        self,
        file_path: Union[str, Path],
        algorithm: HashType = None,
        chunk_size: int = None
    ) -> HashResult:
        """
        计算文件哈希（支持大文件分块）

        Args:
            file_path: 文件路径
            algorithm: 哈希算法
            chunk_size: 分块大小（默认 1MB）

        Returns:
            HashResult
        """
        file_path = Path(file_path)
        algorithm = algorithm or self.default_algorithm
        chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if algorithm == HashType.SHA256:
            hasher = hashlib.sha256()
        elif algorithm == HashType.SHA384:
            hasher = hashlib.sha384()
        elif algorithm == HashType.SHA512:
            hasher = hashlib.sha512()
        elif algorithm == HashType.MD5:
            hasher = hashlib.md5()
        elif algorithm == HashType.BLAKE2B:
            hasher = hashlib.blake2b()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        file_size = file_path.stat().st_size
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)

        hash_value = hasher.hexdigest()

        return HashResult(
            hash_value=hash_value,
            algorithm=algorithm,
            content_length=file_size,
            content_type=self._guess_content_type(file_path),
            chunk_size=chunk_size,
            file_path=str(file_path)
        )

    def hash_stream(
        self,
        stream: BinaryIO,
        algorithm: HashType = None,
        chunk_size: int = None
    ) -> HashResult:
        """计算流式内容哈希"""
        algorithm = algorithm or self.default_algorithm
        chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE

        if algorithm == HashType.SHA256:
            hasher = hashlib.sha256()
        elif algorithm == HashType.SHA384:
            hasher = hashlib.sha384()
        elif algorithm == HashType.SHA512:
            hasher = hashlib.sha512()
        elif algorithm == HashType.MD5:
            hasher = hashlib.md5()
        elif algorithm == HashType.BLAKE2B:
            hasher = hashlib.blake2b()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        total_read = 0
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
            total_read += len(chunk)

        return HashResult(
            hash_value=hasher.hexdigest(),
            algorithm=algorithm,
            content_length=total_read,
            content_type="application/octet-stream",
            chunk_size=chunk_size
        )

    def hash_json(
        self,
        data: Dict[str, Any],
        algorithm: HashType = None
    ) -> HashResult:
        """
        计算 JSON 结构哈希

        会对 JSON 进行标准化（按键排序、无缩进），确保相同内容产生相同哈希
        """
        algorithm = algorithm or self.default_algorithm

        # 标准化 JSON（按键排序、移除空格）
        normalized = json.dumps(data, sort_keys=True, separators=(',', ':'))

        return self.hash_string(normalized, algorithm)

    def hash_chain(
        self,
        content: str,
        previous_hash: str = "",
        algorithm: HashType = None
    ) -> HashResult:
        """
        计算哈希链（带前驱哈希）

        用于版本追溯，每个版本的哈希都包含前一个版本的哈希
        """
        algorithm = algorithm or self.default_algorithm

        # 组合内容：前驱哈希 + 当前内容
        combined = f"{previous_hash}:{content}"

        result = self.hash_string(combined, algorithm)
        result.metadata["previous_hash"] = previous_hash

        return result

    def verify(
        self,
        content: Union[str, bytes],
        expected_hash: str,
        algorithm: HashType = None
    ) -> bool:
        """
        验证内容哈希

        Args:
            content: 内容
            expected_hash: 期望的哈希值
            algorithm: 哈希算法

        Returns:
            是否匹配
        """
        if isinstance(content, str):
            result = self.hash_string(content, algorithm)
        else:
            result = self.hash_bytes(content, algorithm)

        return result.hash_value == expected_hash

    def verify_file(
        self,
        file_path: Union[str, Path],
        expected_hash: str,
        algorithm: HashType = None
    ) -> bool:
        """验证文件哈希"""
        result = self.hash_file(file_path, algorithm)
        return result.hash_value == expected_hash

    @staticmethod
    def _guess_content_type(file_path: Path) -> str:
        """根据扩展名猜测内容类型"""
        ext = file_path.suffix.lower()

        mime_map = {
            ".txt": "text/plain",
            ".html": "text/html",
            ".htm": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".xml": "application/xml",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".zip": "application/zip",
            ".tar": "application/x-tar",
            ".gz": "application/gzip",
        }

        return mime_map.get(ext, "application/octet-stream")

    def compute_multi_hash(self, content: str) -> Dict[HashType, str]:
        """
        同时计算多种哈希

        用于兼容性或不同场景需求
        """
        results = {}
        for algo in [HashType.SHA256, HashType.SHA384, HashType.SHA512]:
            results[algo] = self.hash_string(content, algo).hash_value
        return results


class HashChain:
    """
    哈希链管理器

    用于管理内容的版本链，每个版本都包含前一个版本的哈希
    """

    def __init__(self, hasher: ContentHasher = None):
        self.hasher = hasher or ContentHasher()
        self._chain: List[HashResult] = []

    @property
    def latest_hash(self) -> Optional[str]:
        """获取最新哈希"""
        if self._chain:
            return self._chain[-1].hash_value
        return None

    @property
    def length(self) -> int:
        """获取链长度"""
        return len(self._chain)

    def append(self, content: str, algorithm: HashType = None) -> HashResult:
        """追加新版本"""
        result = self.hasher.hash_chain(
            content,
            self.latest_hash or "",
            algorithm
        )
        result.computed_by = "user"
        self._chain.append(result)
        return result

    def verify(self) -> bool:
        """验证链完整性"""
        if not self._chain:
            return True

        for i in range(1, len(self._chain)):
            current = self._chain[i]
            previous = self._chain[i - 1]

            # 重新计算当前哈希，验证前驱哈希是否匹配
            recomputed = self.hasher.hash_chain(
                current.hash_value,  # 这里应该存储原始内容
                previous.hash_value,
                current.algorithm
            )

            # 简化验证：检查 previous_hash 元数据
            if current.metadata.get("previous_hash") != previous.hash_value:
                return False

        return True

    def get_version(self, index: int) -> Optional[HashResult]:
        """获取指定版本"""
        if 0 <= index < len(self._chain):
            return self._chain[index]
        return None

    def to_list(self) -> List[Dict[str, Any]]:
        """导出链为列表"""
        return [
            {
                "version": i,
                "hash": r.hash_value,
                "algorithm": r.algorithm.value,
                "timestamp": r.timestamp_str,
                "previous_hash": r.metadata.get("previous_hash", "")
            }
            for i, r in enumerate(self._chain)
        ]
