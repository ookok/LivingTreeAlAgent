"""
内容仓库 (Content Store)
========================

类 Git 的文件版本控制系统，支持：
- 快照 (Snapshot)
- 增量同步 (Delta Sync)
- 内容寻址存储 (CAS)

用于知识库文档、模型文件等大文件同步

Author: Hermes Desktop AI Assistant
"""

import os
import json
import time
import hashlib
import logging
import sqlite3
import threading
import zipfile
import io
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================
# 内容寻址存储 (Content Addressable Store)
# ============================================================

class ContentStore:
    """
    内容寻址存储

    使用 SHA256 哈希作为内容ID，实现：
    - 相同内容只存储一次
    - 轻松检测重复和差异
    """

    HASH_SIZE = 32  # SHA256

    def __init__(self, store_dir: str):
        self.store_dir = Path(store_dir)
        self.objects_dir = self.store_dir / "objects"
        self.objects_dir.mkdir(parents=True, exist_ok=True)

        # 内存索引
        self._index: Dict[str, str] = {}  # hash -> file_path
        self._load_index()

    def _hash_content(self, content: bytes) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content).hexdigest()

    def _load_index(self):
        """加载索引"""
        index_file = self.store_dir / "index.json"
        if index_file.exists():
            with open(index_file, 'r') as f:
                self._index = json.load(f)

    def _save_index(self):
        """保存索引"""
        index_file = self.store_dir / "index.json"
        with open(index_file, 'w') as f:
            json.dump(self._index, f, indent=2)

    def _get_object_path(self, hash_id: str) -> Path:
        """获取对象文件路径"""
        # 使用前2个字符作为子目录
        subdir = hash_id[:2]
        return self.objects_dir / subdir / hash_id[2:]

    def has(self, hash_id: str) -> bool:
        """检查内容是否存在"""
        return hash_id in self._index

    def put(self, content: bytes) -> str:
        """
        存储内容

        Returns:
            内容的哈希ID
        """
        hash_id = self._hash_content(content)
        if hash_id in self._index:
            return hash_id

        # 写入文件
        obj_path = self._get_object_path(hash_id)
        obj_path.parent.mkdir(parents=True, exist_ok=True)

        with open(obj_path, 'wb') as f:
            f.write(content)

        self._index[hash_id] = str(obj_path)
        self._save_index()

        return hash_id

    def get(self, hash_id: str) -> Optional[bytes]:
        """获取内容"""
        if hash_id not in self._index:
            return None

        obj_path = Path(self._index[hash_id])
        if not obj_path.exists():
            # 尝试重新定位
            obj_path = self._get_object_path(hash_id)

        if not obj_path.exists():
            return None

        with open(obj_path, 'rb') as f:
            return f.read()

    def delete(self, hash_id: str) -> bool:
        """删除内容"""
        if hash_id not in self._index:
            return False

        obj_path = Path(self._index[hash_id])
        if obj_path.exists():
            obj_path.unlink()

        del self._index[hash_id]
        self._save_index()
        return True

    def list_all(self) -> List[str]:
        """列出所有内容ID"""
        return list(self._index.keys())

    def get_size(self, hash_id: str) -> int:
        """获取内容大小"""
        if hash_id not in self._index:
            return 0

        obj_path = Path(self._index[hash_id])
        if not obj_path.exists():
            obj_path = self._get_object_path(hash_id)

        if obj_path.exists():
            return obj_path.stat().st_size
        return 0


# ============================================================
# 快照与树
# ============================================================

@dataclass
class FileEntry:
    """文件条目"""
    path: str           # 相对于根的路径
    hash_id: str        # 内容哈希
    size: int           # 文件大小
    mode: int           # 文件模式

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "hash_id": self.hash_id,
            "size": self.size,
            "mode": self.mode
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'FileEntry':
        return cls(**data)


@dataclass
class Tree:
    """目录树"""
    entries: List[FileEntry] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    device_id: str = ""

    def to_dict(self) -> dict:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "timestamp": self.timestamp,
            "device_id": self.device_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Tree':
        return cls(
            entries=[FileEntry.from_dict(e) for e in data.get("entries", [])],
            timestamp=data.get("timestamp", 0),
            device_id=data.get("device_id", "")
        )

    def get_hash_id(self) -> str:
        """计算树的哈希"""
        import json
        content = json.dumps(self.to_dict(), sort_keys=True).encode()
        return hashlib.sha256(content).hexdigest()


@dataclass
class Snapshot:
    """快照"""
    tree_hash: str           # 根树哈希
    message: str             # 快照消息
    timestamp: float         # 创建时间
    device_id: str           # 创建设备
    parent_hash: Optional[str] = None  # 父快照哈希
    fingerprint: str = ""    # 内容指纹

    def to_dict(self) -> dict:
        return {
            "tree_hash": self.tree_hash,
            "message": self.message,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "parent_hash": self.parent_hash,
            "fingerprint": self.fingerprint
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Snapshot':
        return cls(**data)

    def get_hash_id(self) -> str:
        """计算快照哈希"""
        content = json.dumps(self.to_dict(), sort_keys=True).encode()
        return hashlib.sha256(content).hexdigest()


# ============================================================
# 内容仓库
# ============================================================

class ContentRepository:
    """
    内容仓库

    管理文件的版本化存储，提供：
    1. 快照创建与恢复
    2. 差异计算（rsync风格）
    3. 内容指纹与差量同步
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS snapshots (
        hash_id TEXT PRIMARY KEY,
        tree_hash TEXT NOT NULL,
        message TEXT,
        timestamp REAL NOT NULL,
        device_id TEXT NOT NULL,
        parent_hash TEXT,
        fingerprint TEXT,
        metadata TEXT
    );

    CREATE TABLE IF NOT EXISTS trees (
        hash_id TEXT PRIMARY KEY,
        entries TEXT NOT NULL,
        timestamp REAL NOT NULL,
        device_id TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sync_manifest (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT NOT NULL,
        last_sync REAL,
        last_snapshot TEXT,
        fingerprint TEXT,
        status TEXT
    );
    """

    def __init__(self, repo_dir: str, device_id: str):
        self.repo_dir = Path(repo_dir)
        self.device_id = device_id

        # 内容存储
        self.store = ContentStore(str(self.repo_dir / "objects"))

        # 数据库
        self.db_path = self.repo_dir / "repo.db"
        self.repo_dir.mkdir(parents=True, exist_ok=True)

        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        with self._lock:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.executescript(self.SCHEMA)
            self._conn.commit()

    def _serialize_tree(self, tree: Tree) -> str:
        """序列化树"""
        return json.dumps(tree.to_dict())

    def _deserialize_tree(self, data: str) -> Tree:
        """反序列化树"""
        return Tree.from_dict(json.loads(data))

    def _save_tree(self, tree: Tree) -> str:
        """保存树"""
        tree.device_id = self.device_id
        tree.timestamp = time.time()
        hash_id = tree.get_hash_id()

        self._conn.execute(
            """INSERT OR REPLACE INTO trees (hash_id, entries, timestamp, device_id)
               VALUES (?, ?, ?, ?)""",
            (hash_id, self._serialize_tree(tree), tree.timestamp, self.device_id)
        )
        self._conn.commit()

        return hash_id

    def _get_tree(self, tree_hash: str) -> Optional[Tree]:
        """获取树"""
        cursor = self._conn.execute(
            "SELECT entries FROM trees WHERE hash_id = ?", (tree_hash,)
        )
        row = cursor.fetchone()
        if row:
            return self._deserialize_tree(row[0])
        return None

    def create_snapshot(self, root_dir: str, message: str = "") -> Snapshot:
        """
        创建快照

        Args:
            root_dir: 要快照的根目录
            message: 快照消息

        Returns:
            创建的快照
        """
        with self._lock:
            root = Path(root_dir)

            # 构建树
            tree = self._build_tree(root, "")

            # 保存树
            tree_hash = self._save_tree(tree)

            # 获取父快照
            parent = self._get_latest_snapshot()
            parent_hash = parent.get_hash_id() if parent else None

            # 计算指纹
            fingerprint = self._calculate_fingerprint(tree)

            # 创建快照
            snapshot = Snapshot(
                tree_hash=tree_hash,
                message=message,
                timestamp=time.time(),
                device_id=self.device_id,
                parent_hash=parent_hash,
                fingerprint=fingerprint
            )

            hash_id = snapshot.get_hash_id()

            self._conn.execute(
                """INSERT OR REPLACE INTO snapshots
                   (hash_id, tree_hash, message, timestamp, device_id, parent_hash, fingerprint)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (hash_id, tree_hash, message, snapshot.timestamp,
                 self.device_id, parent_hash, fingerprint)
            )
            self._conn.commit()

            return snapshot

    def _build_tree(self, root: Path, prefix: str) -> Tree:
        """递归构建树"""
        tree = Tree(device_id=self.device_id)

        if not root.exists():
            return tree

        for item in sorted(root.iterdir()):
            rel_path = f"{prefix}/{item.name}" if prefix else item.name

            if item.is_file():
                # 跳过临时文件和隐藏文件
                if item.name.startswith('.') or item.suffix in ('.tmp', '.lock'):
                    continue

                content = item.read_bytes()
                hash_id = self.store.put(content)
                stat = item.stat()

                tree.entries.append(FileEntry(
                    path=rel_path,
                    hash_id=hash_id,
                    size=len(content),
                    mode=stat.st_mode
                ))

            elif item.is_dir():
                subtree = self._build_tree(item, rel_path)
                subtree_hash = subtree.get_hash_id()
                # 将子树作为特殊条目
                for entry in subtree.entries:
                    tree.entries.append(entry)

        return tree

    def _calculate_fingerprint(self, tree: Tree) -> str:
        """计算内容指纹（目录内容哈希）"""
        # 只包含哈希，不包含路径
        hashes = sorted([e.hash_id for e in tree.entries])
        content = json.dumps(hashes).encode()
        return hashlib.sha256(content).hexdigest()[:16]

    def _get_latest_snapshot(self) -> Optional[Snapshot]:
        """获取最新快照"""
        cursor = self._conn.execute(
            """SELECT hash_id, tree_hash, message, timestamp, device_id, parent_hash, fingerprint
               FROM snapshots ORDER BY timestamp DESC LIMIT 1"""
        )
        row = cursor.fetchone()
        if row:
            return Snapshot(
                tree_hash=row[1], message=row[2], timestamp=row[3],
                device_id=row[4], parent_hash=row[5], fingerprint=row[6]
            )
        return None

    def get_snapshot(self, hash_id: str) -> Optional[Snapshot]:
        """获取快照"""
        cursor = self._conn.execute(
            """SELECT hash_id, tree_hash, message, timestamp, device_id, parent_hash, fingerprint
               FROM snapshots WHERE hash_id = ?""", (hash_id,)
        )
        row = cursor.fetchone()
        if row:
            return Snapshot(
                tree_hash=row[1], message=row[2], timestamp=row[3],
                device_id=row[4], parent_hash=row[5], fingerprint=row[6]
            )
        return None

    def get_all_snapshots(self) -> List[Snapshot]:
        """获取所有快照"""
        cursor = self._conn.execute(
            """SELECT hash_id, tree_hash, message, timestamp, device_id, parent_hash, fingerprint
               FROM snapshots ORDER BY timestamp DESC"""
        )
        return [
            Snapshot(
                tree_hash=row[1], message=row[2], timestamp=row[3],
                device_id=row[4], parent_hash=row[5], fingerprint=row[6]
            )
            for row in cursor.fetchall()
        ]

    def restore_snapshot(self, snapshot_hash: str, target_dir: str) -> bool:
        """
        恢复快照到目录

        Args:
            snapshot_hash: 快照哈希
            target_dir: 目标目录

        Returns:
            是否成功
        """
        with self._lock:
            snapshot = self.get_snapshot(snapshot_hash)
            if not snapshot:
                return False

            tree = self._get_tree(snapshot.tree_hash)
            if not tree:
                return False

            target = Path(target_dir)
            target.mkdir(parents=True, exist_ok=True)

            # 恢复文件
            for entry in tree.entries:
                content = self.store.get(entry.hash_id)
                if content is None:
                    logger.warning(f"Missing content: {entry.hash_id}")
                    continue

                file_path = target / entry.path
                file_path.parent.mkdir(parents=True, exist_ok=True)

                with open(file_path, 'wb') as f:
                    f.write(content)

            return True

    def get_diff(self, snapshot_a: str, snapshot_b: str) -> Dict[str, Any]:
        """
        计算两个快照之间的差异

        Returns:
            差异字典，包含：
            - added: 新增文件
            - removed: 删除文件
            - modified: 修改文件
        """
        with self._lock:
            tree_a = self._get_tree(self.get_snapshot(snapshot_a).tree_hash) if snapshot_a else None
            tree_b = self._get_tree(self.get_snapshot(snapshot_b).tree_hash) if snapshot_b else None

            if not tree_a or not tree_b:
                return {"error": "Snapshot not found"}

            # 构建哈希到路径映射
            files_a = {e.hash_id: e for e in tree_a.entries}
            files_b = {e.hash_id: e for e in tree_b.entries}

            paths_a = {e.path: e for e in tree_a.entries}
            paths_b = {e.path: e for e in tree_b.entries}

            result = {
                "added": [],
                "removed": [],
                "modified": []
            }

            # 新增
            for path, entry in paths_b.items():
                if path not in paths_a:
                    result["added"].append({
                        "path": path,
                        "size": entry.size,
                        "hash_id": entry.hash_id
                    })

            # 删除
            for path, entry in paths_a.items():
                if path not in paths_b:
                    result["removed"].append({
                        "path": path,
                        "size": entry.size
                    })

            # 修改
            for path, entry_b in paths_b.items():
                if path in paths_a:
                    entry_a = paths_a[path]
                    if entry_a.hash_id != entry_b.hash_id:
                        result["modified"].append({
                            "path": path,
                            "old_hash": entry_a.hash_id,
                            "new_hash": entry_b.hash_id,
                            "size": entry_b.size
                        })

            return result

    def get_delta_sync(self, local_snapshot: Optional[str], remote_fingerprint: str) -> Dict[str, Any]:
        """
        获取增量同步数据

        用于rsync风格的差量同步

        Args:
            local_snapshot: 本地最新快照
            remote_fingerprint: 远程内容指纹

        Returns:
            需要同步的文件列表
        """
        with self._lock:
            local = self._get_latest_snapshot()
            if not local:
                return {"mode": "full", "files": []}

            # 如果指纹相同，不需要同步
            if local.fingerprint == remote_fingerprint:
                return {"mode": "none", "files": []}

            # 计算差异
            if local_snapshot:
                diff = self.get_diff(local_snapshot, local.get_hash_id())
            else:
                diff = {"added": [], "removed": [], "modified": []}
                tree = self._get_tree(local.tree_hash)
                if tree:
                    diff["added"] = [
                        {"path": e.path, "size": e.size, "hash_id": e.hash_id}
                        for e in tree.entries
                    ]

            # 收集需要上传的文件
            files_to_sync = []

            for item in diff.get("added", []) + diff.get("modified", []):
                content = self.store.get(item["hash_id"])
                if content:
                    files_to_sync.append({
                        "path": item["path"],
                        "hash_id": item["hash_id"],
                        "size": item["size"],
                        "content": base64.b64encode(content).decode() if len(content) < 1024 * 1024 else None
                        # 大文件不内嵌内容
                    })

            return {
                "mode": "delta",
                "files": files_to_sync,
                "fingerprint": local.fingerprint
            }

    def import_delta(self, delta: Dict[str, Any]):
        """
        导入增量数据

        Args:
            delta: get_delta_sync返回的增量数据
        """
        with self._lock:
            if delta.get("mode") == "none":
                return

            for file_info in delta.get("files", []):
                if "content" in file_info and file_info["content"]:
                    content = base64.b64decode(file_info["content"])
                else:
                    continue

                self.store.put(content)

    def update_sync_manifest(self, device_id: str, snapshot_hash: str, fingerprint: str, status: str = "synced"):
        """更新同步清单"""
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO sync_manifest
                   (device_id, last_sync, last_snapshot, fingerprint, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (device_id, time.time(), snapshot_hash, fingerprint, status)
            )
            self._conn.commit()

    def get_sync_manifest(self, device_id: str) -> Optional[Dict[str, Any]]:
        """获取同步清单"""
        cursor = self._conn.execute(
            """SELECT device_id, last_sync, last_snapshot, fingerprint, status
               FROM sync_manifest WHERE device_id = ?""", (device_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "device_id": row[0],
                "last_sync": row[1],
                "last_snapshot": row[2],
                "fingerprint": row[3],
                "status": row[4]
            }
        return None

    def close(self):
        """关闭数据库"""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None


import base64


# ============================================================
# 全局单例
# ============================================================

_content_repo: Optional[ContentRepository] = None


def get_content_repo(device_id: str = "") -> ContentRepository:
    """获取全局内容仓库"""
    global _content_repo
    if _content_repo is None:
        repo_dir = Path.home() / ".hermes" / "content"
        dev_id = device_id or "local"
        _content_repo = ContentRepository(str(repo_dir), dev_id)
    return _content_repo


def reset_content_repo():
    """重置全局内容仓库"""
    global _content_repo
    if _content_repo:
        _content_repo.close()
    _content_repo = None