"""
块管理器 - Chunk Manager

负责：
- 文件分块与合并
- 块哈希计算
- 块缓存
- 块验证
"""

import asyncio
import hashlib
import os
import json
import aiofiles
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from pathlib import Path
import struct

from .models import BEPChunk, FileInfo, FileType


# 块大小配置
DEFAULT_BLOCK_SIZE = 1024 * 256  # 256KB
MAX_BLOCK_SIZE = 1024 * 1024      # 1MB
MIN_BLOCK_SIZE = 1024             # 1KB


@dataclass
class ChunkStore:
    """块存储"""
    chunk_id: str
    file_id: str
    offset: int
    size: int
    hash: str
    weak_hash: int
    path: str  # 块文件路径
    compressed: bool = False

    @property
    def exists(self) -> bool:
        return os.path.exists(self.path)


class ChunkManager:
    """
    块管理器

    负责将文件分割为块，支持：
    - 固定大小分块
    - 内容定义分块 (CDC)
    - 块缓存
    - 块去重
    """

    def __init__(self, cache_dir: str, block_size: int = DEFAULT_BLOCK_SIZE):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.block_size = block_size
        self._chunks: Dict[str, ChunkStore] = {}  # chunk_id -> ChunkStore
        self._file_chunks: Dict[str, List[str]] = {}  # file_id -> [chunk_ids]
        self._hash_index: Dict[str, str] = {}  # hash -> chunk_id (块去重)

        # 统计
        self._hits = 0
        self._misses = 0

    def set_block_size(self, size: int):
        """设置块大小"""
        if MIN_BLOCK_SIZE <= size <= MAX_BLOCK_SIZE:
            self.block_size = size

    def split_file(self, file_path: str, file_id: str) -> List[BEPChunk]:
        """
        将文件分割为块

        Returns:
            块列表
        """
        chunks = []
        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as f:
            offset = 0
            chunk_index = 0

            while offset < file_size:
                remaining = file_size - offset
                chunk_size = min(self.block_size, remaining)

                data = f.read(chunk_size)
                if not data:
                    break

                # 计算哈希
                strong_hash, weak_hash = BEPChunk.compute_hash(data)

                # 生成块ID
                chunk_id = self._generate_chunk_id(file_id, offset, strong_hash)

                # 检查是否已存在（去重）
                if strong_hash in self._hash_index:
                    # 复用已有块
                    existing_id = self._hash_index[strong_hash]
                    chunk = BEPChunk(
                        chunk_id=existing_id,
                        file_id=file_id,
                        offset=offset,
                        size=len(data),
                        hash=strong_hash,
                        weak_hash=weak_hash,
                    )
                else:
                    # 创建新块
                    chunk = BEPChunk(
                        chunk_id=chunk_id,
                        file_id=file_id,
                        offset=offset,
                        size=len(data),
                        hash=strong_hash,
                        weak_hash=weak_hash,
                    )

                    # 保存块到缓存
                    self._save_chunk(chunk_id, data)

                    # 更新索引
                    self._hash_index[strong_hash] = chunk_id

                chunks.append(chunk)

                # 更新文件-块映射
                if file_id not in self._file_chunks:
                    self._file_chunks[file_id] = []
                self._file_chunks[file_id].append(chunk.chunk_id)

                offset += len(data)
                chunk_index += 1

        return chunks

    async def split_file_async(self, file_path: str, file_id: str) -> List[BEPChunk]:
        """异步分割文件"""
        return await asyncio.to_thread(self.split_file, file_path, file_id)

    def _generate_chunk_id(self, file_id: str, offset: int, hash: str) -> str:
        """生成块ID"""
        data = f"{file_id}:{offset}:{hash}".encode()
        return hashlib.sha256(data).hexdigest()[:32]

    def _save_chunk(self, chunk_id: str, data: bytes):
        """保存块到缓存"""
        chunk_path = self.cache_dir / f"{chunk_id}.chunk"
        with open(chunk_path, "wb") as f:
            f.write(data)

        self._chunks[chunk_id] = ChunkStore(
            chunk_id=chunk_id,
            file_id="",  # 稍后设置
            offset=0,
            size=len(data),
            hash="",  # 稍后设置
            weak_hash=0,
            path=str(chunk_path),
        )

    async def get_chunk(self, chunk_id: str) -> Optional[bytes]:
        """获取块数据"""
        if chunk_id not in self._chunks:
            return None

        chunk = self._chunks[chunk_id]
        if not chunk.exists:
            return None

        try:
            async with aiofiles.open(chunk.path, "rb") as f:
                data = await f.read()
                self._hits += 1
                return data
        except:
            self._misses += 1
            return None

    async def put_chunk(self, chunk_id: str, data: bytes,
                       file_id: str = "", offset: int = 0):
        """存入块数据"""
        chunk_path = self.cache_dir / f"{chunk_id}.chunk"

        async with aiofiles.open(chunk_path, "wb") as f:
            await f.write(data)

        strong_hash, weak_hash = BEPChunk.compute_hash(data)

        store = ChunkStore(
            chunk_id=chunk_id,
            file_id=file_id,
            offset=offset,
            size=len(data),
            hash=strong_hash,
            weak_hash=weak_hash,
            path=str(chunk_path),
        )
        self._chunks[chunk_id] = store
        self._hash_index[strong_hash] = chunk_id

        # 更新文件-块映射
        if file_id:
            if file_id not in self._file_chunks:
                self._file_chunks[file_id] = []
            if chunk_id not in self._file_chunks[file_id]:
                self._file_chunks[file_id].append(chunk_id)

    def merge_file(self, file_id: str, output_path: str,
                   chunks: List[BEPChunk]) -> bool:
        """
        合并块为文件

        Args:
            file_id: 文件ID
            output_path: 输出文件路径
            chunks: 块列表（必须按offset排序）

        Returns:
            是否成功
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, "wb") as f:
                for chunk in sorted(chunks, key=lambda c: c.offset):
                    data = asyncio.run(self.get_chunk(chunk.chunk_id))
                    if data is None:
                        return False
                    f.write(data)

            return True
        except Exception as e:
            return False

    async def merge_file_async(self, file_id: str, output_path: str,
                               chunks: List[BEPChunk]) -> bool:
        """异步合并文件"""
        return await asyncio.to_thread(self.merge_file, file_id, output_path, chunks)

    def verify_chunk(self, chunk_id: str, data: bytes) -> bool:
        """验证块数据"""
        if chunk_id not in self._chunks:
            return False

        chunk = self._chunks[chunk_id]
        strong_hash, weak_hash = BEPChunk.compute_hash(data)

        return strong_hash == chunk.hash and weak_hash == chunk.weak_hash

    def get_file_chunks(self, file_id: str) -> List[str]:
        """获取文件的所有块ID"""
        return self._file_chunks.get(file_id, [])

    def remove_file_chunks(self, file_id: str):
        """移除文件的所有块（但不删除块文件）"""
        if file_id in self._file_chunks:
            del self._file_chunks[file_id]

    def delete_chunk(self, chunk_id: str):
        """删除块文件"""
        if chunk_id in self._chunks:
            chunk = self._chunks[chunk_id]
            try:
                if chunk.exists:
                    os.remove(chunk.path)
            except:
                pass
            del self._chunks[chunk_id]

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_chunks = len(self._chunks)
        total_size = sum(c.size for c in self._chunks.values())

        cache_size = sum(
            os.path.getsize(f.path)
            for f in self._chunks.values()
            if f.exists
        ) if self._chunks else 0

        return {
            "total_chunks": total_chunks,
            "total_size": total_size,
            "cache_size": cache_size,
            "unique_files": len(self._file_chunks),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0,
        }

    def clear_cache(self, keep_chunks: Optional[Set[str]] = None):
        """清理缓存"""
        if keep_chunks is None:
            keep_chunks = set()

        to_delete = [cid for cid in self._chunks if cid not in keep_chunks]

        for chunk_id in to_delete:
            self.delete_chunk(chunk_id)

        # 清理孤儿块文件
        for chunk_file in self.cache_dir.glob("*.chunk"):
            if chunk_file.stem not in self._chunks:
                try:
                    chunk_file.unlink()
                except:
                    pass

    def load_index(self, index_path: str):
        """加载块索引"""
        try:
            with open(index_path, "r") as f:
                data = json.load(f)

            self._chunks = {
                cid: ChunkStore(**chunk)
                for cid, chunk in data.get("chunks", {}).items()
            }
            self._file_chunks = data.get("file_chunks", {})
            self._hash_index = data.get("hash_index", {})

        except Exception:
            pass

    def save_index(self, index_path: str):
        """保存块索引"""
        data = {
            "chunks": {
                cid: {
                    "chunk_id": c.chunk_id,
                    "file_id": c.file_id,
                    "offset": c.offset,
                    "size": c.size,
                    "hash": c.hash,
                    "weak_hash": c.weak_hash,
                    "path": c.path,
                    "compressed": c.compressed,
                }
                for cid, c in self._chunks.items()
            },
            "file_chunks": self._file_chunks,
            "hash_index": self._hash_index,
        }

        with open(index_path, "w") as f:
            json.dump(data, f)


class ContentDefinedChunker:
    """
    内容定义分块器 (CDC)

    基于内容特征自动确定分块边界，
    比固定分块更适合增量同步
    """

    # 滚动哈希参数
    MASK_BITS = 13  # 2^13 = 8192
    MASK = (1 << MASK_BITS) - 1

    # 分块参数
    MIN_BLOCK_SIZE = 1024      # 最小块
    MAX_BLOCK_SIZE = 1024 * 64 # 最大块

    def __init__(self, avg_block_size: int = 4096):
        self.avg_block_size = avg_block_size

    def _roll_hash(self, data: bytes, pos: int, c: int, c_star: int) -> int:
        """滚动哈希计算"""
        if pos == 0:
            return sum((data[i] * (self.avg_block_size ** (self.MASK_BITS - 1 - i))) & 0xFFFF
                      for i in range(min(len(data), self.MASK_BITS)))

        # 更新哈希
        d = data[pos + self.MIN_BLOCK_SIZE - 1] if pos + self.MIN_BLOCK_SIZE - 1 < len(data) else 0
        return ((c * self.avg_block_size) - (c_star * self.avg_block_size) + d) & 0xFFFF

    def chunk(self, data: bytes) -> List[Tuple[int, int]]:
        """
        分块

        Returns:
            [(offset, length), ...] 块列表
        """
        chunks = []
        pos = 0
        current_hash = 0

        # 初始化窗口
        if len(data) < self.MIN_BLOCK_SIZE:
            return [(0, len(data))]

        # 计算第一个窗口的哈希
        for i in range(self.MIN_BLOCK_SIZE):
            current_hash = (current_hash * 31 + data[i]) & 0xFFFF

        while pos < len(data):
            chunk_start = pos

            # 寻找分块点
            found = False
            while pos - chunk_start < self.MAX_BLOCK_SIZE - self.MIN_BLOCK_SIZE and pos + self.MIN_BLOCK_SIZE < len(data):
                pos += 1
                current_hash = (current_hash * 31 + data[pos + self.MIN_BLOCK_SIZE - 1]) & 0xFFFF
                old_char = data[pos - self.MIN_BLOCK_SIZE]

                # 检查是否为分块点
                if current_hash & self.MASK == self.MASK:
                    found = True
                    break

            if not found:
                # 没有找到分块点，使用最大块大小
                pos = min(chunk_start + self.MAX_BLOCK_SIZE, len(data))

            chunks.append((chunk_start, pos - chunk_start))
            chunk_start = pos

        return chunks
