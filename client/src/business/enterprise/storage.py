"""
企业存储系统
Enterprise Storage System

基于P2P CDN的企业虚拟网盘系统，整合节点管理和虚拟文件系统
"""

from __future__ import annotations

import asyncio
import logging
import time
import hashlib
import json
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from client.src.business.p2p_cdn import P2PCDN, create_p2p_cdn
from .node_manager import EnterpriseNodeManager, EnterpriseNode, get_enterprise_manager
from .virtual_filesystem import VirtualFileSystem, VirtualFile, VirtualFolder

logger = logging.getLogger(__name__)


class EnterpriseStorage:
    """企业存储系统"""

    def __init__(self, enterprise_id: str, node_id: str):
        self.enterprise_id = enterprise_id
        self.node_id = node_id
        self.node_manager = get_enterprise_manager(enterprise_id)
        self.virtual_fs = VirtualFileSystem()
        self.p2p_cdn: Optional[P2PCDN] = None
        self.data_dir = Path(f"~/.enterprise_storage/{enterprise_id}/{node_id}").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.fs_metadata_file = self.data_dir / "fs_metadata.json"
        
        # 初始化版本控制
        from .version_control import get_version_control
        self.version_control = get_version_control()
        
        # 初始化权限管理
        from .permission import get_permission_manager
        self.permission_manager = get_permission_manager()
        
        # 初始化文件预览
        from .file_preview import get_file_previewer
        self.file_previewer = get_file_previewer()
        
        # 初始化同步管理
        from .sync import get_sync_manager
        self.sync_manager = get_sync_manager()

    async def start(self):
        """启动企业存储系统"""
        logger.info(f"Starting Enterprise Storage for {self.enterprise_id}...")

        # 启动节点管理器
        await self.node_manager.start()

        # 初始化 P2P CDN
        self.p2p_cdn = await create_p2p_cdn(
            node_id=self.node_id,
            data_dir=str(self.data_dir / "p2p_cdn"),
            max_cache_size=1024 * 1024 * 1024 * 10  # 10GB
        )

        # 启动本地文件管理器
        from .local_file_manager import get_local_file_manager
        local_file_manager = get_local_file_manager()
        await local_file_manager.start()

        # 加载文件系统元数据
        self._load_fs_metadata()

        # 注册当前节点
        await self._register_current_node()

        logger.info(f"Enterprise Storage started successfully")

    async def stop(self):
        """停止企业存储系统"""
        logger.info(f"Stopping Enterprise Storage for {self.enterprise_id}...")

        # 保存文件系统元数据
        self._save_fs_metadata()

        # 停止 P2P CDN
        if self.p2p_cdn:
            await self.p2p_cdn.stop()

        # 停止本地文件管理器
        from .local_file_manager import get_local_file_manager
        local_file_manager = get_local_file_manager()
        await local_file_manager.stop()

        # 停止节点管理器
        await self.node_manager.stop()

        logger.info(f"Enterprise Storage stopped")

    async def _register_current_node(self):
        """注册当前节点"""
        # 计算节点能力
        from client.src.business.p2p_cdn import NodeCapability
        capability = NodeCapability(
            storage_available=1024 * 1024 * 1024 * 50,  # 50GB
            bandwidth=1000,  # 1Gbps
            uptime=3600,  # 1小时
            reliability=0.99  # 99% 可靠性
        )

        # 创建企业节点
        node = EnterpriseNode(
            node_id=self.node_id,
            name=f"Node-{self.node_id[:8]}",
            ip="127.0.0.1",  # 实际应使用真实IP
            port=8000,  # 实际应使用真实端口
            capability=capability,
            role="worker",
            status="online"
        )

        # 添加节点
        self.node_manager.add_node(node)

    def _load_fs_metadata(self):
        """加载文件系统元数据"""
        if self.fs_metadata_file.exists():
            try:
                with open(self.fs_metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.virtual_fs = VirtualFileSystem.from_dict(data)
                logger.info("File system metadata loaded")
            except Exception as e:
                logger.error(f"Failed to load file system metadata: {e}")

    def _save_fs_metadata(self):
        """保存文件系统元数据"""
        try:
            with open(self.fs_metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.virtual_fs.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info("File system metadata saved")
        except Exception as e:
            logger.error(f"Failed to save file system metadata: {e}")

    async def create_folder(self, name: str, parent_id: str, owner: str) -> str:
        """创建文件夹"""
        folder_id = self.virtual_fs.create_folder(name, parent_id, owner)
        self._save_fs_metadata()
        return folder_id

    async def upload_file(self, name: str, parent_id: str, content: bytes, mime_type: str, owner: str, comment: str = "") -> str:
        """上传文件"""
        # 创建文件记录
        file_id = self.virtual_fs.create_file(name, parent_id, len(content), mime_type, owner)
        file = self.virtual_fs.get_item(file_id)

        if not isinstance(file, VirtualFile):
            raise ValueError("Failed to create file")

        # 计算文件校验和
        checksum = hashlib.sha256(content).hexdigest()
        file.checksum = checksum

        # 选择存储节点
        storage_nodes = await self._select_storage_nodes(len(content), 3)  # 3副本
        file.replicas = [node.node_id for node in storage_nodes]

        # 存储文件数据到 P2P CDN
        file_data = {
            "content": content.hex(),
            "checksum": checksum,
            "size": len(content),
            "mime_type": mime_type
        }

        data_id = await self.p2p_cdn.store_data(file_data)
        logger.info(f"File {name} stored with data_id: {data_id}")

        # 更新文件元数据
        file.metadata["data_id"] = data_id
        file.metadata["file_type"] = "remote"
        
        # 创建版本
        self.version_control.create_version(
            file_id=file_id,
            size=len(content),
            checksum=checksum,
            created_by=owner,
            comment=comment,
            metadata={"data_id": data_id}
        )
        
        self._save_fs_metadata()

        return file_id

    async def upload_local_file(self, name: str, parent_id: str, local_path: str, owner: str, comment: str = "") -> str:
        """上传本地文件（只记录路径）"""
        from .local_file_manager import get_local_file_manager

        # 检查本地文件是否存在
        import os
        if not os.path.exists(local_path):
            raise ValueError(f"Local file does not exist: {local_path}")

        # 获取文件信息
        import mimetypes
        from pathlib import Path
        path = Path(local_path)
        size = self._get_local_file_size(local_path)
        mime_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"

        # 计算文件校验和（对于本地文件，使用路径和大小作为校验和）
        checksum = hashlib.sha256(f"{local_path}:{size}:{os.path.getmtime(local_path)}".encode()).hexdigest()

        # 创建文件记录
        file_id = self.virtual_fs.create_file(name, parent_id, size, mime_type, owner)
        file = self.virtual_fs.get_item(file_id)

        if not isinstance(file, VirtualFile):
            raise ValueError("Failed to create file")

        # 更新文件元数据
        file.metadata["local_path"] = local_path
        file.metadata["file_type"] = "local"
        file.metadata["is_directory"] = path.is_dir()
        file.replicas = [self.node_id]  # 本地文件只有一个副本
        file.checksum = checksum

        # 添加到本地文件管理器
        local_file_manager = get_local_file_manager()
        local_file_manager.add_local_file(file_id, local_path)

        # 创建版本
        self.version_control.create_version(
            file_id=file_id,
            size=size,
            checksum=checksum,
            created_by=owner,
            comment=comment,
            metadata={"local_path": local_path}
        )

        self._save_fs_metadata()
        logger.info(f"Local file {name} added with path: {local_path}")

        return file_id

    def _get_local_file_size(self, local_path: str) -> int:
        """获取本地文件或文件夹大小"""
        import os
        from pathlib import Path
        path = Path(local_path)
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(local_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(filepath)
            return total_size
        return 0

    async def download_file(self, file_id: str) -> Optional[bytes]:
        """下载文件"""
        file = self.virtual_fs.get_item(file_id)
        if not isinstance(file, VirtualFile):
            return None

        # 检查文件类型
        file_type = file.metadata.get("file_type", "remote")

        if file_type == "local":
            # 处理本地文件
            local_path = file.metadata.get("local_path")
            if not local_path:
                return None

            import os
            if not os.path.exists(local_path):
                logger.warning(f"Local file not found: {local_path}")
                return None

            # 检查是否是目录
            is_directory = file.metadata.get("is_directory", False)
            if is_directory:
                # 对于目录，返回目录信息
                import json
                dir_info = {
                    "type": "directory",
                    "path": local_path,
                    "files": []
                }
                for root, dirs, files in os.walk(local_path):
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        rel_path = os.path.relpath(file_path, local_path)
                        dir_info["files"].append({
                            "name": file_name,
                            "path": rel_path,
                            "size": os.path.getsize(file_path)
                        })
                return json.dumps(dir_info).encode()
            else:
                # 对于文件，返回文件内容
                try:
                    with open(local_path, "rb") as f:
                        content = f.read()
                    return content
                except Exception as e:
                    logger.error(f"Failed to read local file: {e}")
                    return None
        else:
            # 处理远程文件
            data_id = file.metadata.get("data_id")
            if not data_id:
                return None

            data = await self.p2p_cdn.get_data(data_id)
            if not data:
                return None

            # 解码内容
            content_hex = data.get("content")
            if not content_hex:
                return None

            try:
                content = bytes.fromhex(content_hex)
                return content
            except Exception as e:
                logger.error(f"Failed to decode file content: {e}")
                return None

    async def delete_file(self, file_id: str) -> bool:
        """删除文件"""
        file = self.virtual_fs.get_item(file_id)
        if not isinstance(file, VirtualFile):
            return False

        # 检查文件类型
        file_type = file.metadata.get("file_type", "remote")

        if file_type == "local":
            # 处理本地文件 - 只删除记录，不删除实际文件
            from .local_file_manager import get_local_file_manager
            local_file_manager = get_local_file_manager()
            local_file_manager.remove_local_file(file_id)
            logger.info(f"Local file record deleted: {file_id}")
        else:
            # 处理远程文件
            data_id = file.metadata.get("data_id")
            if data_id and self.p2p_cdn:
                await self.p2p_cdn.delete_data(data_id)

        # 从虚拟文件系统删除
        result = self.virtual_fs.delete_item(file_id)
        if result:
            self._save_fs_metadata()
        return result

    async def delete_folder(self, folder_id: str) -> bool:
        """删除文件夹"""
        # 检查文件夹是否为空
        folder = self.virtual_fs.get_item(folder_id)
        if not isinstance(folder, VirtualFolder):
            return False

        if folder.children:
            raise ValueError("Folder is not empty")

        # 从虚拟文件系统删除
        result = self.virtual_fs.delete_item(folder_id)
        if result:
            self._save_fs_metadata()
        return result

    async def list_folder(self, folder_id: str) -> Dict[str, Any]:
        """列出文件夹内容"""
        return self.virtual_fs.list_folder(folder_id)

    async def move_item(self, item_id: str, new_parent_id: str, new_name: Optional[str] = None) -> bool:
        """移动文件或文件夹"""
        result = self.virtual_fs.move_item(item_id, new_parent_id, new_name)
        if result:
            self._save_fs_metadata()
        return result

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """搜索文件和文件夹"""
        return self.virtual_fs.search(query)

    async def get_item_info(self, item_id: str) -> Optional[Dict[str, Any]]:
        """获取项目信息"""
        item = self.virtual_fs.get_item(item_id)
        if not item:
            return None

        info = {
            "id": item_id,
            "name": item.name,
            "created_at": item.created_at,
            "modified_at": item.modified_at,
            "owner": item.owner,
            "permissions": item.permissions,
            "path": self.virtual_fs.get_path(item_id)
        }

        if isinstance(item, VirtualFile):
            info.update({
                "type": "file",
                "size": item.size,
                "mime_type": item.mime_type,
                "replicas": item.replicas,
                "checksum": item.checksum
            })

            # 检查是否是本地文件
            file_type = item.metadata.get("file_type", "remote")
            info["file_type"] = file_type

            if file_type == "local":
                # 获取本地文件信息
                from .local_file_manager import get_local_file_manager
                local_file_manager = get_local_file_manager()
                local_file_info = local_file_manager.get_local_file(item_id)
                if local_file_info:
                    info.update({
                        "local_path": local_file_info.get("local_path"),
                        "is_directory": local_file_info.get("is_directory"),
                        "status": local_file_info.get("status"),
                        "last_checked": local_file_info.get("last_checked")
                    })
        elif isinstance(item, VirtualFolder):
            info.update({
                "type": "folder",
                "children_count": len(item.children)
            })

        return info

    async def _select_storage_nodes(self, file_size: int, replica_count: int) -> List[EnterpriseNode]:
        """选择存储节点"""
        # 获取在线节点
        online_nodes = self.node_manager.get_nodes(status="online")

        # 按可用存储空间排序
        online_nodes.sort(key=lambda x: x.capability.storage_available, reverse=True)

        # 选择前 N 个节点
        selected_nodes = []
        for node in online_nodes:
            if len(selected_nodes) >= replica_count:
                break
            if node.capability.storage_available >= file_size:
                selected_nodes.append(node)
                # 预分配存储空间
                self.node_manager.allocate_storage(node.node_id, file_size)

        return selected_nodes

    async def get_file_versions(self, file_id: str) -> List[Dict[str, Any]]:
        """获取文件的所有版本"""
        versions = self.version_control.get_all_versions(file_id)
        return [version.to_dict() for version in versions]

    async def get_file_version(self, file_id: str, version_number: int) -> Optional[Dict[str, Any]]:
        """获取文件的特定版本"""
        version = self.version_control.get_version(file_id, version_number)
        return version.to_dict() if version else None

    async def rollback_to_version(self, file_id: str, version_number: int, user_id: str) -> Optional[Dict[str, Any]]:
        """回滚到指定版本"""
        version = self.version_control.rollback_to_version(file_id, version_number)
        return version.to_dict() if version else None

    async def delete_file_version(self, file_id: str, version_number: int) -> bool:
        """删除文件版本"""
        return self.version_control.delete_version(file_id, version_number)

    async def grant_permission(self, subject_type: str, subject_id: str, resource_id: str, actions: List[str]) -> Dict[str, Any]:
        """授予权限"""
        permission = self.permission_manager.grant_permission(
            subject_type=subject_type,
            subject_id=subject_id,
            resource_id=resource_id,
            actions=set(actions)
        )
        return permission.to_dict()

    async def deny_permission(self, subject_type: str, subject_id: str, resource_id: str, actions: List[str]) -> Dict[str, Any]:
        """拒绝权限"""
        permission = self.permission_manager.deny_permission(
            subject_type=subject_type,
            subject_id=subject_id,
            resource_id=resource_id,
            actions=set(actions)
        )
        return permission.to_dict()

    async def check_permission(self, user_id: str, resource_id: str, action: str) -> bool:
        """检查用户是否有执行操作的权限"""
        return self.permission_manager.check_permission(user_id, resource_id, action)

    async def add_user_to_group(self, user_id: str, group_id: str):
        """添加用户到组"""
        self.permission_manager.add_user_to_group(user_id, group_id)

    async def generate_file_preview(self, file_id: str) -> Dict[str, Any]:
        """生成文件预览"""
        file = self.virtual_fs.get_item(file_id)
        if not isinstance(file, VirtualFile):
            return {"success": False, "message": "Not a file"}

        # 检查文件类型
        file_type = file.metadata.get("file_type", "remote")

        if file_type == "local":
            local_path = file.metadata.get("local_path")
            if not local_path:
                return {"success": False, "message": "Local path not found"}

            import os
            if not os.path.exists(local_path):
                return {"success": False, "message": "Local file not found"}

            # 检查是否是目录
            is_directory = file.metadata.get("is_directory", False)
            if is_directory:
                return {"success": False, "message": "Cannot preview directory"}

            # 生成预览
            return self.file_previewer.generate_preview(file.name, local_path)
        else:
            # 对于远程文件，先下载内容再预览
            content = await self.download_file(file_id)
            if not content:
                return {"success": False, "message": "Failed to download file"}

            # 临时保存文件
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=f".{file.name.split('.')[-1]}", delete=False) as f:
                f.write(content)
                temp_path = f.name

            try:
                # 生成预览
                preview = self.file_previewer.generate_preview(file.name, temp_path)
                return preview
            finally:
                # 清理临时文件
                import os
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

    async def create_sync_job(self, job_id: str, local_root: str, cloud_root: str, direction: str) -> Dict[str, Any]:
        """创建同步任务"""
        from .sync import DummyCloudAdapter
        # 创建模拟云存储适配器
        adapter = DummyCloudAdapter(cloud_root)
        # 创建同步任务
        job = self.sync_manager.create_sync_job(
            job_id=job_id,
            local_root=local_root,
            cloud_root=cloud_root,
            direction=direction,
            adapter=adapter
        )
        return job.to_dict()

    async def start_sync_job(self, job_id: str) -> bool:
        """启动同步任务"""
        return await self.sync_manager.start_sync_job(job_id)

    async def stop_sync_job(self, job_id: str) -> bool:
        """停止同步任务"""
        return await self.sync_manager.stop_sync_job(job_id)

    async def get_sync_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """获取同步任务信息"""
        job = self.sync_manager.get_sync_job(job_id)
        return job.to_dict() if job else None

    async def list_sync_jobs(self) -> List[Dict[str, Any]]:
        """列出所有同步任务"""
        return self.sync_manager.list_sync_jobs()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        node_stats = self.node_manager.get_stats()
        fs_stats = {
            "total_files": len(self.virtual_fs.files),
            "total_folders": len(self.virtual_fs.folders),
            "root_folder_id": self.virtual_fs.root_folder_id
        }
        version_stats = self.version_control.get_stats()
        permission_stats = self.permission_manager.get_stats()

        return {
            "enterprise_id": self.enterprise_id,
            "node_id": self.node_id,
            **node_stats,
            **fs_stats,
            **version_stats,
            **permission_stats
        }


# 单例管理
enterprise_storages: Dict[str, Dict[str, EnterpriseStorage]] = {}


def get_enterprise_storage(enterprise_id: str, node_id: str) -> EnterpriseStorage:
    """获取企业存储系统"""
    if enterprise_id not in enterprise_storages:
        enterprise_storages[enterprise_id] = {}
    if node_id not in enterprise_storages[enterprise_id]:
        enterprise_storages[enterprise_id][node_id] = EnterpriseStorage(enterprise_id, node_id)
    return enterprise_storages[enterprise_id][node_id]


def list_enterprise_storages() -> List[Tuple[str, str]]:
    """列出所有企业存储系统"""
    result = []
    for enterprise_id, nodes in enterprise_storages.items():
        for node_id in nodes:
            result.append((enterprise_id, node_id))
    return result
