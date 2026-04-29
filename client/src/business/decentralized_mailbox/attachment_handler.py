"""
附件与大信处理

实现大文件分片、加密、上传、下载
from __future__ import annotations
"""


import asyncio
import hashlib
import logging
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, List

from .models import Attachment, AttachmentType

logger = logging.getLogger(__name__)


class AttachmentHandler:
    """
    附件处理器
    
    功能:
    - 小文件直接加密存储
    - 大文件分片加密
    - 断点续传
    - 云盘上传/下载
    """
    
    # 分片配置
    CHUNK_SIZE = 512 * 1024       # 512KB per chunk
    MAX_DIRECT_SIZE = 2 * 1024 * 1024  # 2MB 以下直接存
    MAX_MEMORY_CHUNK = 10 * 1024 * 1024  # 10MB 以下内存处理
    
    # 存储配置
    LOCAL_STORAGE_DIR = "~/.hermes-desktop/mailbox/attachments"
    CLOUD_STORAGE_PREFIX = "/mailbox/attachments/"
    
    def __init__(self, storage_dir: str = None, crypto=None):
        self.storage_dir = Path(storage_dir or self.LOCAL_STORAGE_DIR).expanduser()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.crypto = crypto  # 加密器
        
        # 上传/下载进度回调
        self._progress_callbacks: dict[str, Callable] = {}
        
        # 分片追踪
        self._upload_progress: dict[str, dict] = {}
        self._download_progress: dict[str, dict] = {}
        
        # 云盘集成 (复用virtual_storage)
        self._cloud_storage = None
    
    def set_crypto(self, crypto):
        """设置加密器"""
        self.crypto = crypto
    
    def set_cloud_storage(self, storage):
        """设置云存储"""
        self._cloud_storage = storage
    
    # ========== 附件上传 ==========
    
    async def upload_attachment(self, file_path: str, 
                               message_id: str,
                               progress_callback: Optional[Callable] = None
                               ) -> Optional[List[Attachment]]:
        """
        上传附件
        
        Args:
            file_path: 文件路径
            message_id: 关联的消息ID
            progress_callback: 进度回调 (chunk_index, total, speed)
            
        Returns:
            List[Attachment] or None
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"File not found: {file_path}")
                return None
            
            file_size = path.stat().st_size
            file_hash = await self._compute_file_hash(file_path)
            
            # 选择存储方式
            if file_size <= self.MAX_DIRECT_SIZE:
                # 小文件: 直接加密存储
                return [await self._upload_small_file(path, message_id, file_hash)]
            else:
                # 大文件: 分片加密
                return await self._upload_large_file(path, message_id, file_hash, 
                                                     progress_callback)
        
        except Exception as e:
            logger.error(f"Upload attachment failed: {e}")
            return None
    
    async def _upload_small_file(self, path: Path, message_id: str, 
                                 checksum: str) -> Attachment:
        """上传小文件"""
        # 读取文件
        data = path.read_bytes()
        
        # 加密
        if self.crypto:
            ciphertext, iv, salt = self.crypto.encrypt_chunk(data)
            # 存储时附带IV和salt
            encrypted_data = salt + iv + ciphertext
        else:
            encrypted_data = data
        
        # 生成chunk_id
        chunk_id = f"{message_id}_{path.stem}_{checksum[:8]}"
        
        # 保存到本地
        storage_path = self.storage_dir / f"{chunk_id}.enc"
        storage_path.write_bytes(encrypted_data)
        
        # 创建附件记录
        attachment = Attachment(
            chunk_id=chunk_id,
            filename=path.name,
            file_size=len(data),
            content_type=self._guess_content_type(path.name),
            checksum=checksum,
            total_chunks=1,
            chunk_index=0,
            storage_path=str(storage_path),
            status=AttachmentType.FILE
        )
        
        logger.debug(f"Uploaded small file: {path.name} -> {chunk_id}")
        return attachment
    
    async def _upload_large_file(self, path: Path, message_id: str,
                                 checksum: str,
                                 progress_callback: Optional[Callable] = None
                                 ) -> List[Attachment]:
        """上传大文件 (分片)"""
        file_size = path.stat().st_size
        total_chunks = (file_size + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE
        
        attachments = []
        upload_id = f"{message_id}_{path.stem}"
        
        # 初始化进度追踪
        self._upload_progress[upload_id] = {
            "total_chunks": total_chunks,
            "completed_chunks": 0,
            "total_size": file_size,
            "uploaded_size": 0,
            "start_time": time.time()
        }
        self._progress_callbacks[upload_id] = progress_callback
        
        try:
            with open(path, "rb") as f:
                for i in range(total_chunks):
                    # 读取分片
                    chunk_data = f.read(self.CHUNK_SIZE)
                    
                    # 加密分片
                    if self.crypto:
                        ciphertext, nonce, key_id = self.crypto.encrypt_chunk(chunk_data)
                        encrypted_chunk = key_id + nonce + ciphertext
                    else:
                        encrypted_chunk = chunk_data
                    
                    # 生成chunk_id
                    chunk_id = f"{upload_id}_c{i:04d}_{checksum[:8]}"
                    
                    # 选择存储目标
                    if self._cloud_storage and self._should_use_cloud(len(encrypted_chunk)):
                        # 云存储
                        storage_path = f"{self.CLOUD_STORAGE_PREFIX}{chunk_id}"
                        success = await self._cloud_storage.upload(encrypted_chunk, storage_path)
                        if not success:
                            # 回退到本地
                            storage_path = str(self.storage_dir / f"{chunk_id}.enc")
                            self.storage_dir.mkdir(parents=True, exist_ok=True)
                            (Path(storage_path).write_bytes(encrypted_chunk))
                    else:
                        # 本地存储
                        storage_path = str(self.storage_dir / f"{chunk_id}.enc")
                        self.storage_dir.mkdir(parents=True, exist_ok=True)
                        (Path(storage_path).write_bytes(encrypted_chunk))
                    
                    # 创建附件记录
                    attachment = Attachment(
                        chunk_id=chunk_id,
                        filename=path.name,
                        file_size=len(chunk_data),
                        content_type=self._guess_content_type(path.name),
                        checksum=self.hash_data(chunk_data),
                        total_chunks=total_chunks,
                        chunk_index=i,
                        storage_path=storage_path,
                        upload_progress=(i + 1) / total_chunks,
                        status=AttachmentType.ENCRYPTED_CHUNK if self.crypto else AttachmentType.LARGE_FILE
                    )
                    attachments.append(attachment)
                    
                    # 更新进度
                    self._upload_progress[upload_id]["completed_chunks"] += 1
                    self._upload_progress[upload_id]["uploaded_size"] += len(chunk_data)
                    
                    if progress_callback:
                        progress_callback(i, total_chunks, 
                                         self._calc_speed(upload_id))
            
            logger.info(f"Uploaded large file: {path.name} in {total_chunks} chunks")
            return attachments
            
        finally:
            self._upload_progress.pop(upload_id, None)
            self._progress_callbacks.pop(upload_id, None)
    
    # ========== 附件下载 ==========
    
    async def download_attachment(self, attachment: Attachment,
                                 output_path: str,
                                 progress_callback: Optional[Callable] = None
                                 ) -> bool:
        """
        下载附件
        
        Args:
            attachment: 附件信息
            output_path: 输出文件路径
            progress_callback: 进度回调
            
        Returns:
            bool: 是否成功
        """
        try:
            if attachment.total_chunks == 1:
                return await self._download_small_file(attachment, output_path)
            else:
                return await self._download_large_file(attachment, output_path,
                                                      progress_callback)
        except Exception as e:
            logger.error(f"Download attachment failed: {e}")
            return False
    
    async def _download_small_file(self, attachment: Attachment,
                                   output_path: str) -> bool:
        """下载小文件"""
        if not attachment.storage_path:
            logger.error("No storage path for attachment")
            return False
        
        storage_path = Path(attachment.storage_path)
        if not storage_path.exists():
            # 尝试从云存储下载
            if self._cloud_storage:
                data = await self._cloud_storage.download(attachment.storage_path)
                if data:
                    Path(output_path).write_bytes(data)
                    return True
            return False
        
        # 读取并解密
        encrypted_data = storage_path.read_bytes()
        
        if self.crypto and attachment.status == AttachmentType.FILE:
            # 提取salt, iv, ciphertext
            salt = encrypted_data[:16]
            iv = encrypted_data[16:28]
            ciphertext = encrypted_data[28:]
            
            # 解密 (使用固定密钥派生, 实际应用中应存储密钥ID)
            plaintext = self.crypto.decrypt_chunk(ciphertext, iv, b'default', 
                                                  lambda k: self.crypto.get_shared_key('default'))
            if plaintext:
                Path(output_path).write_bytes(plaintext)
                return True
        else:
            Path(output_path).write_bytes(encrypted_data)
            return True
        
        return False
    
    async def _download_large_file(self, attachment: Attachment,
                                   output_path: str,
                                   progress_callback: Optional[Callable] = None) -> bool:
        """下载大文件 (合并分片)"""
        download_id = attachment.chunk_id.rsplit("_", 2)[0]
        
        self._download_progress[download_id] = {
            "total_chunks": attachment.total_chunks,
            "completed_chunks": 0,
            "start_time": time.time()
        }
        
        try:
            with open(output_path, "wb") as f:
                for i in range(attachment.total_chunks):
                    # 构造分片ID
                    chunk_id = f"{download_id}_c{i:04d}_{attachment.checksum[:8]}"
                    storage_path = self.storage_dir / f"{chunk_id}.enc"
                    
                    # 尝试本地
                    if not storage_path.exists() and self._cloud_storage:
                        cloud_path = f"{self.CLOUD_STORAGE_PREFIX}{chunk_id}"
                        chunk_data = await self._cloud_storage.download(cloud_path)
                    elif storage_path.exists():
                        chunk_data = storage_path.read_bytes()
                    else:
                        logger.error(f"Chunk not found: {chunk_id}")
                        return False
                    
                    # 解密
                    if self.crypto:
                        # 提取key_id, nonce, ciphertext
                        key_id = chunk_data[:8]
                        nonce = chunk_data[8:16]
                        ciphertext = chunk_data[16:]
                        
                        plaintext = self.crypto.decrypt_chunk(ciphertext, nonce, key_id,
                                                            self.crypto.get_shared_key)
                        if plaintext:
                            f.write(plaintext)
                        else:
                            return False
                    else:
                        f.write(chunk_data)
                    
                    # 更新进度
                    self._download_progress[download_id]["completed_chunks"] += 1
                    if progress_callback:
                        progress_callback(i + 1, attachment.total_chunks,
                                        self._calc_download_speed(download_id))
            
            logger.info(f"Downloaded large file: {attachment.filename}")
            return True
            
        finally:
            self._download_progress.pop(download_id, None)
    
    # ========== 辅助方法 ==========
    
    def _should_use_cloud(self, chunk_size: int) -> bool:
        """判断是否应使用云存储"""
        # 大于1MB或本地空间不足时使用云存储
        if chunk_size > 1024 * 1024:
            return True
        
        # 检查本地空间
        import shutil
        total, used, free = shutil.disk_usage(self.storage_dir)
        if free < 100 * 1024 * 1024:  # 小于100MB
            return True
        
        return False
    
    async def _compute_file_hash(self, file_path: str) -> str:
        """计算文件SHA256哈希"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    @staticmethod
    def hash_data(data: bytes) -> str:
        """计算数据哈希"""
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def _guess_content_type(filename: str) -> str:
        """猜测MIME类型"""
        ext = Path(filename).suffix.lower()
        types = {
            ".txt": "text/plain",
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".xml": "application/xml",
            ".pdf": "application/pdf",
            ".zip": "application/zip",
            ".rar": "application/vnd.rar",
            ".7z": "application/x-7z-compressed",
            ".tar": "application/x-tar",
            ".gz": "application/gzip",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".svg": "image/svg+xml",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
        return types.get(ext, "application/octet-stream")
    
    def _calc_speed(self, upload_id: str) -> float:
        """计算上传速度 (bytes/s)"""
        if upload_id not in self._upload_progress:
            return 0
        
        progress = self._upload_progress[upload_id]
        elapsed = time.time() - progress["start_time"]
        if elapsed > 0:
            return progress["uploaded_size"] / elapsed
        return 0
    
    def _calc_download_speed(self, download_id: str) -> float:
        """计算下载速度 (bytes/s)"""
        if download_id not in self._download_progress:
            return 0
        
        progress = self._download_progress[download_id]
        elapsed = time.time() - progress["start_time"]
        if elapsed > 0:
            chunk_size = self.CHUNK_SIZE
            return (progress["completed_chunks"] * chunk_size) / elapsed
        return 0
    
    # ========== 附件管理 ==========
    
    def delete_attachment(self, attachment: Attachment) -> bool:
        """删除附件"""
        try:
            if attachment.storage_path:
                path = Path(attachment.storage_path)
                if path.exists():
                    path.unlink()
                
                # 如果是分片, 删除所有分片
                if attachment.total_chunks > 1:
                    base_id = attachment.chunk_id.rsplit("_", 2)[0]
                    for i in range(attachment.total_chunks):
                        chunk_path = self.storage_dir / f"{base_id}_c{i:04d}_{attachment.checksum[:8]}.enc"
                        if chunk_path.exists():
                            chunk_path.unlink()
            
            logger.debug(f"Deleted attachment: {attachment.chunk_id}")
            return True
        except Exception as e:
            logger.error(f"Delete attachment failed: {e}")
            return False
    
    def get_attachment_size(self, attachment: Attachment) -> int:
        """获取附件总大小"""
        if attachment.total_chunks == 1:
            return attachment.file_size
        return attachment.file_size * attachment.total_chunks
    
    def verify_attachment(self, attachment: Attachment) -> bool:
        """验证附件完整性"""
        # TODO: 实现校验和验证
        return True
