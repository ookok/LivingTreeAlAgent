"""
虚拟文件系统
Virtual File System

实现企业内的虚拟文件系统，支持文件夹式的可视化管理
from __future__ import annotations
"""


import time
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class VirtualFile:
    """虚拟文件模型"""
    file_id: str
    name: str
    size: int
    mime_type: str
    owner: str
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    permissions: str = "rwxrwxrwx"
    replicas: List[str] = field(default_factory=list)
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "file_id": self.file_id,
            "name": self.name,
            "size": self.size,
            "mime_type": self.mime_type,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "owner": self.owner,
            "permissions": self.permissions,
            "replicas": self.replicas,
            "checksum": self.checksum,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VirtualFile:
        """从字典创建"""
        return cls(
            file_id=data.get("file_id"),
            name=data.get("name"),
            size=data.get("size", 0),
            mime_type=data.get("mime_type", "application/octet-stream"),
            created_at=data.get("created_at", time.time()),
            modified_at=data.get("modified_at", time.time()),
            owner=data.get("owner"),
            permissions=data.get("permissions", "rwxrwxrwx"),
            replicas=data.get("replicas", []),
            checksum=data.get("checksum"),
            metadata=data.get("metadata", {})
        )


@dataclass
class VirtualFolder:
    """虚拟文件夹模型"""
    folder_id: str
    name: str
    owner: str
    parent_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    permissions: str = "rwxrwxrwx"
    children: Dict[str, str] = field(default_factory=dict)  # {name: item_id}
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "folder_id": self.folder_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "owner": self.owner,
            "permissions": self.permissions,
            "children": self.children,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VirtualFolder:
        """从字典创建"""
        return cls(
            folder_id=data.get("folder_id"),
            name=data.get("name"),
            owner=data.get("owner"),
            parent_id=data.get("parent_id"),
            created_at=data.get("created_at", time.time()),
            modified_at=data.get("modified_at", time.time()),
            permissions=data.get("permissions", "rwxrwxrwx"),
            children=data.get("children", {}),
            metadata=data.get("metadata", {})
        )


class VirtualFileSystem:
    """虚拟文件系统"""

    def __init__(self):
        self.files: Dict[str, VirtualFile] = {}
        self.folders: Dict[str, VirtualFolder] = {}
        self.root_folder_id = self._create_root_folder()

    def _create_root_folder(self) -> str:
        """创建根文件夹"""
        root_id = hashlib.sha256("root".encode()).hexdigest()
        root_folder = VirtualFolder(
            folder_id=root_id,
            name="root",
            owner="system",
            parent_id=None,
            permissions="rwxrwxrwx"
        )
        self.folders[root_id] = root_folder
        return root_id

    def create_folder(self, name: str, parent_id: str, owner: str) -> str:
        """创建文件夹"""
        # 检查父文件夹是否存在
        if parent_id not in self.folders:
            raise ValueError(f"Parent folder {parent_id} not found")

        # 检查同名文件夹是否存在
        parent_folder = self.folders[parent_id]
        if name in parent_folder.children:
            raise ValueError(f"Folder {name} already exists in parent folder")

        # 创建新文件夹
        folder_id = hashlib.sha256(f"{parent_id}:{name}:{time.time()}".encode()).hexdigest()
        new_folder = VirtualFolder(
            folder_id=folder_id,
            name=name,
            parent_id=parent_id,
            owner=owner
        )

        # 添加到文件夹列表
        self.folders[folder_id] = new_folder

        # 添加到父文件夹的子项
        parent_folder.children[name] = folder_id
        parent_folder.modified_at = time.time()

        return folder_id

    def create_file(self, name: str, parent_id: str, size: int, mime_type: str, owner: str) -> str:
        """创建文件"""
        # 检查父文件夹是否存在
        if parent_id not in self.folders:
            raise ValueError(f"Parent folder {parent_id} not found")

        # 检查同名文件是否存在
        parent_folder = self.folders[parent_id]
        if name in parent_folder.children:
            raise ValueError(f"File {name} already exists in parent folder")

        # 创建新文件
        file_id = hashlib.sha256(f"{parent_id}:{name}:{time.time()}".encode()).hexdigest()
        new_file = VirtualFile(
            file_id=file_id,
            name=name,
            size=size,
            mime_type=mime_type,
            owner=owner
        )

        # 添加到文件列表
        self.files[file_id] = new_file

        # 添加到父文件夹的子项
        parent_folder.children[name] = file_id
        parent_folder.modified_at = time.time()

        return file_id

    def delete_item(self, item_id: str) -> bool:
        """删除文件或文件夹"""
        # 检查是文件还是文件夹
        if item_id in self.files:
            # 是文件
            file = self.files[item_id]
            # 查找父文件夹
            for folder_id, folder in self.folders.items():
                for name, child_id in folder.children.items():
                    if child_id == item_id:
                        del folder.children[name]
                        folder.modified_at = time.time()
                        break
            del self.files[item_id]
            return True
        elif item_id in self.folders:
            # 是文件夹
            folder = self.folders[item_id]
            # 检查是否有子项
            if folder.children:
                raise ValueError(f"Folder {folder.name} is not empty")
            # 查找父文件夹
            for parent_id, parent_folder in self.folders.items():
                for name, child_id in parent_folder.children.items():
                    if child_id == item_id:
                        del parent_folder.children[name]
                        parent_folder.modified_at = time.time()
                        break
            del self.folders[item_id]
            return True
        return False

    def move_item(self, item_id: str, new_parent_id: str, new_name: Optional[str] = None) -> bool:
        """移动文件或文件夹"""
        # 检查新父文件夹是否存在
        if new_parent_id not in self.folders:
            raise ValueError(f"New parent folder {new_parent_id} not found")

        # 检查是文件还是文件夹
        if item_id in self.files:
            item = self.files[item_id]
            item_type = "file"
        elif item_id in self.folders:
            item = self.folders[item_id]
            item_type = "folder"
        else:
            return False

        # 查找旧父文件夹
        old_parent_id = None
        old_name = None
        for folder_id, folder in self.folders.items():
            for name, child_id in folder.children.items():
                if child_id == item_id:
                    old_parent_id = folder_id
                    old_name = name
                    break
            if old_parent_id:
                break

        if not old_parent_id:
            return False

        # 检查新位置是否有同名项
        new_parent_folder = self.folders[new_parent_id]
        target_name = new_name or old_name
        if target_name in new_parent_folder.children:
            raise ValueError(f"Item {target_name} already exists in new parent folder")

        # 从旧父文件夹移除
        del self.folders[old_parent_id].children[old_name]
        self.folders[old_parent_id].modified_at = time.time()

        # 添加到新父文件夹
        new_parent_folder.children[target_name] = item_id
        new_parent_folder.modified_at = time.time()

        # 更新项目名称
        if new_name and item_type == "file":
            item.name = new_name
            item.modified_at = time.time()
        elif new_name and item_type == "folder":
            item.name = new_name
            item.modified_at = time.time()

        return True

    def get_item(self, item_id: str) -> Optional[Any]:
        """获取文件或文件夹"""
        if item_id in self.files:
            return self.files[item_id]
        elif item_id in self.folders:
            return self.folders[item_id]
        return None

    def list_folder(self, folder_id: str) -> Dict[str, Any]:
        """列出文件夹内容"""
        if folder_id not in self.folders:
            raise ValueError(f"Folder {folder_id} not found")

        folder = self.folders[folder_id]
        contents = {
            "folders": [],
            "files": []
        }

        for name, child_id in folder.children.items():
            if child_id in self.folders:
                contents["folders"].append({
                    "id": child_id,
                    "name": name,
                    "type": "folder",
                    "created_at": self.folders[child_id].created_at,
                    "modified_at": self.folders[child_id].modified_at,
                    "owner": self.folders[child_id].owner
                })
            elif child_id in self.files:
                contents["files"].append({
                    "id": child_id,
                    "name": name,
                    "type": "file",
                    "size": self.files[child_id].size,
                    "mime_type": self.files[child_id].mime_type,
                    "created_at": self.files[child_id].created_at,
                    "modified_at": self.files[child_id].modified_at,
                    "owner": self.files[child_id].owner
                })

        return contents

    def get_path(self, item_id: str) -> str:
        """获取项目的路径"""
        path_parts = []
        current_id = item_id

        while current_id:
            if current_id in self.files:
                item = self.files[current_id]
                path_parts.insert(0, item.name)
                # 查找父文件夹
                for folder_id, folder in self.folders.items():
                    if item_id in folder.children.values():
                        current_id = folder_id
                        break
                else:
                    current_id = None
            elif current_id in self.folders:
                item = self.folders[current_id]
                path_parts.insert(0, item.name)
                current_id = item.parent_id
            else:
                break

        return "/" + "/".join(path_parts)

    def search(self, query: str) -> List[Dict[str, Any]]:
        """搜索文件和文件夹"""
        results = []

        # 搜索文件
        for file_id, file in self.files.items():
            if query.lower() in file.name.lower():
                results.append({
                    "id": file_id,
                    "name": file.name,
                    "type": "file",
                    "size": file.size,
                    "path": self.get_path(file_id)
                })

        # 搜索文件夹
        for folder_id, folder in self.folders.items():
            if query.lower() in folder.name.lower():
                results.append({
                    "id": folder_id,
                    "name": folder.name,
                    "type": "folder",
                    "path": self.get_path(folder_id)
                })

        return results

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "files": {file_id: file.to_dict() for file_id, file in self.files.items()},
            "folders": {folder_id: folder.to_dict() for folder_id, folder in self.folders.items()},
            "root_folder_id": self.root_folder_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VirtualFileSystem:
        """从字典创建"""
        fs = cls()
        fs.files = {
            file_id: VirtualFile.from_dict(file_data)
            for file_id, file_data in data.get("files", {}).items()
        }
        fs.folders = {
            folder_id: VirtualFolder.from_dict(folder_data)
            for folder_id, folder_data in data.get("folders", {}).items()
        }
        fs.root_folder_id = data.get("root_folder_id", fs.root_folder_id)
        return fs
