"""
AliDriver - 阿里云盘驱动

基于 aligo SDK 实现的阿里云盘驱动
参考: https://github.com/foyoux/aligo
"""

import asyncio
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Optional

from core.cloud_drivers.base_driver import (
    BaseCloudDriver,
    CloudEntry,
    CloudProvider,
    CloudQuota,
    DriverConfig,
    EntryType,
)


class AliDriver(BaseCloudDriver):
    """
    阿里云盘驱动

    使用 aligo SDK 实现阿里云盘的各种操作
    """

    def __init__(self, config: DriverConfig):
        super().__init__(config)
        self._client = None  # aligo.Aligo 实例
        self._user_info = None

    # ── 认证 ─────────────────────────────────────────────────────

    async def login(self, **credentials) -> bool:
        """
        阿里云盘登录

        Args:
            credentials: {"refresh_token": "xxx"}
        """
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            return False

        try:
            import aligo

            # 创建客户端
            self._client = aligo.Aligo(
                refresh_token=refresh_token,
                name=f"hermes_{self.config.name}"
            )

            # 验证登录
            self._user_info = await asyncio.to_thread(self._client.get_user_info)
            self._authenticated = True
            return True

        except Exception as e:
            self._authenticated = False
            return False

    async def logout(self) -> bool:
        """退出登录"""
        if self._client:
            try:
                await asyncio.to_thread(self._client.logout)
            except Exception:
                pass
        self._authenticated = False
        self._client = None
        self._user_info = None
        return True

    async def refresh_token(self) -> bool:
        """刷新访问令牌"""
        if not self._client:
            return False

        try:
            await asyncio.to_thread(self._client.refresh_token)
            return True
        except Exception:
            return False

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated and self._client is not None

    # ── 文件操作 ─────────────────────────────────────────────────────

    async def list(
        self,
        path: str = "/",
        page_size: int = 100,
        page_token: Optional[str] = None
    ) -> tuple[list[CloudEntry], Optional[str]]:
        """列出目录内容"""
        if not self._client:
            return [], None

        try:
            # 获取文件列表
            result = await asyncio.to_thread(
                self._client.get_file_list,
                folder_id=self._path_to_file_id(path),
                limit=page_size,
                page=page_token
            )

            entries = []
            next_token = None

            if isinstance(result, dict):
                files = result.get("files", [])
                next_token = result.get("next_page_token")
            else:
                files = result if hasattr(result, "__iter__") else []

            for f in files:
                entry = self._convert_file_to_entry(f)
                if entry:
                    entries.append(entry)

            return entries, next_token

        except Exception as e:
            return [], None

    async def stat(self, path: str) -> Optional[CloudEntry]:
        """获取文件/目录信息"""
        if not self._client:
            return None

        try:
            # 获取文件详情
            file_id = self._path_to_file_id(path)

            if file_id == "root":
                # 根目录
                return CloudEntry(
                    path=path,
                    name=self.config.name,
                    entry_type=EntryType.FOLDER,
                    cloud=self.config.name,
                    real_id="root"
                )

            result = await asyncio.to_thread(
                self._client.get_file_by_id,
                file_id
            )

            if result:
                return self._convert_file_to_entry(result)

            return None

        except Exception:
            return None

    async def download(
        self,
        path: str,
        dest: BinaryIO,
        progress_callback: Optional[callable] = None,
        offset: int = 0,
        length: Optional[int] = None
    ) -> int:
        """下载文件"""
        if not self._client:
            raise RuntimeError("Not authenticated")

        file_id = self._path_to_file_id(path)
        total_bytes = 0

        def _write_chunk(chunk: bytes):
            nonlocal total_bytes
            dest.write(chunk)
            total_bytes += len(chunk)
            if progress_callback:
                progress_callback(total_bytes, 0)  # 0 表示未知总大小

        try:
            await asyncio.to_thread(
                self._client.download_file,
                file_id=file_id,
                dest=dest,
                offset=offset,
                length=length
            )
            return total_bytes

        except Exception as e:
            raise RuntimeError(f"Download failed: {e}")

    async def upload(
        self,
        source: BinaryIO,
        dest_path: str,
        size: int,
        progress_callback: Optional[callable] = None,
        if_not_exists: bool = True
    ) -> Optional[CloudEntry]:
        """上传文件"""
        if not self._client:
            raise RuntimeError("Not authenticated")

        try:
            # 获取父目录和文件名
            parent_path = str(Path(dest_path).parent)
            file_name = Path(dest_path).name
            parent_id = self._path_to_file_id(parent_path)

            # 秒传检测
            if if_not_exists:
                hash_value = await self._calculate_hash(source, size)
                source.seek(0)

                rapid_upload_result = await asyncio.to_thread(
                    self._client.rapid_upload,
                    file_name=file_name,
                    file_size=size,
                    file_hash=hash_value,
                    parent_file_id=parent_id
                )

                if rapid_upload_result:
                    return self._convert_file_to_entry(rapid_upload_result)

            # 普通上传
            def _read_chunk():
                return source.read(1024 * 1024)  # 1MB chunks

            result = await asyncio.to_thread(
                self._client.upload_file,
                file_name=file_name,
                file_size=size,
                read_chunk=_read_chunk,
                parent_file_id=parent_id
            )

            if result:
                return self._convert_file_to_entry(result)

            return None

        except Exception as e:
            raise RuntimeError(f"Upload failed: {e}")

    async def delete(self, path: str, permanently: bool = False) -> bool:
        """删除文件"""
        if not self._client:
            return False

        file_id = self._path_to_file_id(path)

        try:
            await asyncio.to_thread(
                self._client.delete_file,
                file_id=file_id,
                drive_id=self._get_drive_id()
            )
            return True
        except Exception:
            return False

    async def move(self, src_path: str, dest_path: str) -> bool:
        """移动文件"""
        if not self._client:
            return False

        src_id = self._path_to_file_id(src_path)
        dest_parent = str(Path(dest_path).parent)
        dest_parent_id = self._path_to_file_id(dest_parent)
        dest_name = Path(dest_path).name

        try:
            await asyncio.to_thread(
                self._client.move_file,
                file_id=src_id,
                new_parent_id=dest_parent_id,
                new_name=dest_name,
                drive_id=self._get_drive_id()
            )
            return True
        except Exception:
            return False

    async def copy(self, src_path: str, dest_path: str) -> bool:
        """复制文件"""
        if not self._client:
            return False

        src_id = self._path_to_file_id(src_path)
        dest_parent = str(Path(dest_path).parent)
        dest_parent_id = self._path_to_file_id(dest_parent)
        dest_name = Path(dest_path).name

        try:
            await asyncio.to_thread(
                self._client.copy_file,
                file_id=src_id,
                new_parent_id=dest_parent_id,
                new_name=dest_name,
                drive_id=self._get_drive_id()
            )
            return True
        except Exception:
            return False

    async def create_folder(self, path: str) -> Optional[CloudEntry]:
        """创建目录"""
        if not self._client:
            raise RuntimeError("Not authenticated")

        parent_path = str(Path(path).parent)
        folder_name = Path(path).name
        parent_id = self._path_to_file_id(parent_path)

        try:
            result = await asyncio.to_thread(
                self._client.create_folder,
                name=folder_name,
                parent_id=parent_id,
                drive_id=self._get_drive_id()
            )

            if result:
                return self._convert_file_to_entry(result)

            return None

        except Exception:
            return None

    # ── 元数据 ─────────────────────────────────────────────────────

    async def get_quota(self) -> CloudQuota:
        """获取云盘配额"""
        if not self._client:
            return CloudQuota()

        try:
            result = await asyncio.to_thread(self._client.get_drive)

            if isinstance(result, dict):
                return CloudQuota(
                    total=int(result.get("total_size", 0)),
                    used=int(result.get("used_size", 0)),
                    free=int(result.get("total_size", 0)) - int(result.get("used_size", 0)),
                    quota_type=result.get("drive_name", "unknown")
                )
            elif hasattr(result, "total_size"):
                return CloudQuota(
                    total=int(result.total_size),
                    used=int(result.used_size or 0),
                    free=int(result.total_size) - int(result.used_size or 0),
                    quota_type=getattr(result, "drive_name", "unknown")
                )

            return CloudQuota()

        except Exception:
            return CloudQuota()

    async def get_user_info(self) -> dict:
        """获取用户信息"""
        if not self._client:
            return {}

        try:
            if not self._user_info:
                self._user_info = await asyncio.to_thread(self._client.get_user_info)

            if hasattr(self._user_info, "__dict__"):
                return vars(self._user_info)
            elif isinstance(self._user_info, dict):
                return self._user_info
            else:
                return {}

        except Exception:
            return {}

    # ── 分享 ─────────────────────────────────────────────────────

    async def share(
        self,
        path: str,
        password: Optional[str] = None,
        expire_days: Optional[int] = None
    ) -> tuple[str, Optional[str]]:
        """创建分享链接"""
        if not self._client:
            return "", None

        file_id = self._path_to_file_id(path)

        try:
            result = await asyncio.to_thread(
                self._client.create_share_link,
                file_id=file_id,
                drive_id=self._get_drive_id(),
                password=password,
                expire_time=expire_days
            )

            share_id = result.get("share_id", "") if isinstance(result, dict) else getattr(result, "share_id", "")
            share_url = f"https://www.aliyundrive.com/s/{share_id}"

            return share_url, password

        except Exception:
            return "", None

    async def get_share_info(self, share_token: str) -> dict:
        """获取分享信息"""
        if not self._client:
            return {}

        try:
            result = await asyncio.to_thread(
                self._client.get_share_info,
                share_token=share_token
            )

            if hasattr(result, "__dict__"):
                return vars(result)
            return {}

        except Exception:
            return {}

    async def download_from_share(
        self,
        share_token: str,
        password: Optional[str],
        path: str,
        dest: BinaryIO
    ) -> int:
        """从分享链接下载"""
        if not self._client:
            raise RuntimeError("Not authenticated")

        try:
            # 验证分享
            await asyncio.to_thread(
                self._client.get_share_token,
                share_token=share_token,
                password=password
            )

            file_id = self._path_to_file_id(path)

            total_bytes = 0

            def _write_chunk(chunk: bytes):
                nonlocal total_bytes
                dest.write(chunk)
                total_bytes += len(chunk)

            await asyncio.to_thread(
                self._client.download_shared_file,
                file_id=file_id,
                share_token=share_token,
                dest=dest
            )

            return total_bytes

        except Exception as e:
            raise RuntimeError(f"Share download failed: {e}")

    # ── 辅助方法 ─────────────────────────────────────────────────────

    def _path_to_file_id(self, path: str) -> str:
        """将虚拟路径转换为阿里云盘文件ID"""
        # 这里需要维护路径->file_id 的映射
        # 简化处理：使用固定映射或缓存
        if path == "/" or path == "":
            return "root"

        # 从路径提取 name
        name = path.strip("/").split("/")[-1]
        return name  # 简化：实际需要查询

    def _get_drive_id(self) -> str:
        """获取当前 drive_id"""
        if self._client:
            return getattr(self._client, "drive_id", "")
        return ""

    def _convert_file_to_entry(self, file_obj: Any) -> Optional[CloudEntry]:
        """将阿里云盘文件对象转换为 CloudEntry"""
        if not file_obj:
            return None

        try:
            # 处理不同的对象格式
            if hasattr(file_obj, "__dict__"):
                data = vars(file_obj)
            elif isinstance(file_obj, dict):
                data = file_obj
            else:
                return None

            return CloudEntry(
                path=data.get("path", data.get("name", "")),
                name=data.get("name", ""),
                entry_type=EntryType.FOLDER if data.get("type") == "folder" else EntryType.FILE,
                size=int(data.get("size", 0)),
                cloud=self.config.name,
                real_id=data.get("file_id", ""),
                parent_id=data.get("parent_file_id", ""),
                etag=data.get("content_hash", ""),
            )

        except Exception:
            return None

    async def _calculate_hash(self, source: BinaryIO, size: int) -> str:
        """计算文件 SHA1 (秒传用)"""
        sha1 = hashlib.sha1()
        chunk_size = 1024 * 1024  # 1MB

        read = 0
        while read < size:
            chunk = source.read(min(chunk_size, size - read))
            if not chunk:
                break
            sha1.update(chunk)
            read += len(chunk)

        source.seek(0)
        return sha1.hexdigest()
