"""
虚拟云存储模块

实现多云盘统一接口、分布式文件管理
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .models import StorageProvider, FileChunk, MAX_CHUNK_SIZE, CHUNK_SIZE

logger = logging.getLogger(__name__)


class StorageProviderBase(ABC):
    """存储提供商基类"""
    
    @abstractmethod
    async def upload(self, data: bytes, path: str) -> bool:
        """上传文件"""
        pass
    
    @abstractmethod
    async def download(self, path: str) -> Optional[bytes]:
        """下载文件"""
        pass
    
    @abstractmethod
    async def delete(self, path: str) -> bool:
        """删除文件"""
        pass
    
    @abstractmethod
    async def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        pass
    
    @abstractmethod
    async def get_size(self, path: str) -> int:
        """获取文件大小"""
        pass
    
    @abstractmethod
    def get_available_space(self) -> int:
        """获取可用空间"""
        pass


class LocalStorageProvider(StorageProviderBase):
    """本地存储"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    async def upload(self, data: bytes, path: str) -> bool:
        try:
            full_path = self.base_path / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(data)
            return True
        except Exception as e:
            logger.error(f"Local upload failed: {e}")
            return False
    
    async def download(self, path: str) -> Optional[bytes]:
        try:
            full_path = self.base_path / path
            if full_path.exists():
                return full_path.read_bytes()
            return None
        except Exception as e:
            logger.error(f"Local download failed: {e}")
            return None
    
    async def delete(self, path: str) -> bool:
        try:
            full_path = self.base_path / path
            if full_path.exists():
                full_path.unlink()
            return True
        except Exception as e:
            logger.error(f"Local delete failed: {e}")
            return False
    
    async def exists(self, path: str) -> bool:
        return (self.base_path / path).exists()
    
    async def get_size(self, path: str) -> int:
        full_path = self.base_path / path
        if full_path.exists():
            return full_path.stat().st_size
        return 0
    
    def get_available_space(self) -> int:
        import shutil
        return shutil.disk_usage(self.base_path).free


class CloudStorageProvider(StorageProviderBase):
    """云存储基类"""
    
    def __init__(self, provider: StorageProvider):
        self.provider = provider
        self.api_endpoint = provider.api_endpoint
        self.credentials = provider.credentials
    
    async def upload(self, data: bytes, path: str) -> bool:
        """子类实现"""
        raise NotImplementedError
    
    async def download(self, path: str) -> Optional[bytes]:
        """子类实现"""
        raise NotImplementedError
    
    async def delete(self, path: str) -> bool:
        """子类实现"""
        raise NotImplementedError
    
    async def exists(self, path: str) -> bool:
        """子类实现"""
        raise NotImplementedError
    
    async def get_size(self, path: str) -> int:
        """子类实现"""
        raise NotImplementedError
    
    def get_available_space(self) -> int:
        return self.provider.get_available_space()


class VirtualStorage:
    """虚拟云存储管理器"""
    
    def __init__(self):
        self.providers: dict[str, StorageProvider] = {}
        self.storage_backends: dict[str, StorageProviderBase] = {}
        self.file_index: dict[str, list[FileChunk]] = {}  # file_id -> chunks
        
        # 存储策略
        self.small_file_threshold = 10 * 1024 * 1024  # 10MB
        self.medium_file_threshold = 100 * 1024 * 1024  # 100MB
        
        # 本地存储（默认）
        self.add_provider(StorageProvider(
            provider_id="local",
            name="Local Storage",
            provider_type="local",
            enabled=True,
            total_space=0,
            priority=100
        ))
    
    def add_provider(self, provider: StorageProvider) -> bool:
        """添加存储提供商"""
        try:
            self.providers[provider.provider_id] = provider
            
            # 创建存储后端
            if provider.provider_type == "local":
                base_path = provider.credentials.get("path", f"~/.hermes-storage/{provider.provider_id}")
                self.storage_backends[provider.provider_id] = LocalStorageProvider(base_path)
            
            # TODO: 其他云存储类型
            # elif provider.provider_type == "baidu":
            #     self.storage_backends[provider.provider_id] = BaiduStorageProvider(provider)
            
            logger.info(f"Added storage provider: {provider.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add provider: {e}")
            return False
    
    def remove_provider(self, provider_id: str) -> bool:
        """移除存储提供商"""
        if provider_id in self.providers:
            del self.providers[provider_id]
            if provider_id in self.storage_backends:
                del self.storage_backends[provider_id]
            return True
        return False
    
    def get_best_provider(self, file_size: int) -> Optional[str]:
        """获取最佳存储提供商"""
        available = [
            (pid, p) for pid, p in self.providers.items()
            if p.enabled and p.get_available_space() > file_size
        ]
        
        if not available:
            return None
        
        # 按优先级和可用空间排序
        available.sort(key=lambda x: (-x[1].priority, -x[1].get_available_space()))
        return available[0][0]
    
    async def upload_file(
        self,
        data: bytes,
        filename: str,
        user_id: str,
        redundancy: int = 1
    ) -> Optional[str]:
        """上传文件"""
        file_size = len(data)
        file_id = uuid.uuid4().hex
        
        # 确定存储策略
        if file_size <= self.small_file_threshold:
            # 小文件：单提供商
            provider_id = self.get_best_provider(file_size)
            if not provider_id:
                return None
            
            chunk = FileChunk(
                file_id=file_id,
                chunk_index=0,
                size=file_size,
                checksum=hashlib.md5(data).hexdigest(),
                provider_id=provider_id
            )
            
            path = f"{user_id}/{file_id}/{filename}"
            backend = self.storage_backends.get(provider_id)
            if backend and await backend.upload(data, path):
                self.file_index[file_id] = [chunk]
                return file_id
        
        else:
            # 大文件：分块存储
            chunks = self._chunk_data(data, CHUNK_SIZE)
            providers = self._select_redundant_providers(len(chunks), redundancy)
            
            if len(providers) < redundancy:
                return None
            
            file_chunks = []
            success = True
            
            for i, chunk_data in enumerate(chunks):
                chunk = FileChunk(
                    file_id=file_id,
                    chunk_index=i,
                    size=len(chunk_data),
                    checksum=hashlib.md5(chunk_data).hexdigest(),
                    provider_id=providers[i % len(providers)]
                )
                
                path = f"{user_id}/{file_id}/chunk_{i}"
                backend = self.storage_backends.get(chunk.provider_id)
                
                if backend and await backend.upload(chunk_data, path):
                    chunk.storage_path = path
                    file_chunks.append(chunk)
                else:
                    success = False
            
            if success:
                self.file_index[file_id] = file_chunks
                return file_id
        
        return None
    
    async def download_file(self, file_id: str) -> Optional[bytes]:
        """下载文件"""
        if file_id not in self.file_index:
            return None
        
        chunks = self.file_index[file_id]
        
        if len(chunks) == 1:
            # 单块文件
            chunk = chunks[0]
            backend = self.storage_backends.get(chunk.provider_id)
            if backend and chunk.storage_path:
                return await backend.download(chunk.storage_path)
        
        else:
            # 多块文件，按顺序合并
            data_parts = []
            
            for i in range(len(chunks)):
                chunk = next((c for c in chunks if c.chunk_index == i), None)
                if not chunk:
                    return None
                
                backend = self.storage_backends.get(chunk.provider_id)
                if not backend or not chunk.storage_path:
                    return None
                
                part = await backend.download(chunk.storage_path)
                if part is None:
                    return None
                
                data_parts.append(part)
            
            return b''.join(data_parts)
        
        return None
    
    async def delete_file(self, file_id: str) -> bool:
        """删除文件"""
        if file_id not in self.file_index:
            return False
        
        chunks = self.file_index[file_id]
        success = True
        
        for chunk in chunks:
            backend = self.storage_backends.get(chunk.provider_id)
            if backend and chunk.storage_path:
                if not await backend.delete(chunk.storage_path):
                    success = False
        
        del self.file_index[file_id]
        return success
    
    async def file_exists(self, file_id: str) -> bool:
        """检查文件是否存在"""
        if file_id not in self.file_index:
            return False
        
        chunks = self.file_index[file_id]
        return all(
            self.storage_backends.get(c.provider_id) and
            (self.storage_backends[c.provider_id].exists(c.storage_path) if c.storage_path else False)
            for c in chunks
        )
    
    def get_file_info(self, file_id: str) -> Optional[dict]:
        """获取文件信息"""
        if file_id not in self.file_index:
            return None
        
        chunks = self.file_index[file_id]
        return {
            "file_id": file_id,
            "total_size": sum(c.size for c in chunks),
            "chunk_count": len(chunks),
            "providers": list(set(c.provider_id for c in chunks))
        }
    
    def _chunk_data(self, data: bytes, chunk_size: int) -> list[bytes]:
        """分块数据"""
        return [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
    
    def _select_redundant_providers(self, count: int, redundancy: int) -> list[str]:
        """选择冗余提供商"""
        available = [
            pid for pid, p in self.providers.items()
            if p.enabled and p.supports_chunking
        ]
        
        if len(available) < redundancy:
            return available * ((redundancy // len(available) + 1) if available else 0)
        
        return available[:redundancy * count]
    
    def get_storage_stats(self) -> dict:
        """获取存储统计"""
        total_used = 0
        total_space = 0
        provider_stats = {}
        
        for pid, provider in self.providers.items():
            backend = self.storage_backends.get(pid)
            if backend:
                available = backend.get_available_space()
                used = provider.total_space - available if provider.total_space else 0
                total_used += used
                total_space += provider.total_space or available + used
                
                provider_stats[pid] = {
                    "name": provider.name,
                    "total": provider.total_space,
                    "used": used,
                    "available": available,
                    "enabled": provider.enabled
                }
        
        return {
            "total_used": total_used,
            "total_space": total_space,
            "file_count": len(self.file_index),
            "provider_count": len(self.providers),
            "providers": provider_stats
        }


# ============= 便捷函数 =============

def create_local_storage(path: str = "~/.hermes-storage/local") -> VirtualStorage:
    """创建本地虚拟存储"""
    storage = VirtualStorage()
    storage.add_provider(StorageProvider(
        provider_id="local",
        name="Local",
        provider_type="local",
        credentials={"path": path}
    ))
    return storage
