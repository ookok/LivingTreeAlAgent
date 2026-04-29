"""
智能表单 - P2P数据同步器
将表单数据安全地存储和同步到P2P网络

核心：加密存储、分布式备份、版本管理
"""

import json
import hashlib
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, AsyncGenerator
from enum import Enum
from datetime import datetime
import copy


# ==================== 数据模型 ====================

class DataSource(Enum):
    """数据来源"""
    AI_EXTRACT = "ai_extract"         # AI从文档提取
    OWNER_INPUT = "owner_input"       # 业主手动输入
    KNOWLEDGE_BASE = "knowledge_base"  # 知识库标准值
    CROSS_REFERENCE = "cross_ref"     # 跨表单引用


@dataclass
class FormDataChunk:
    """表单数据块"""
    chunk_id: str
    data: Dict
    source: DataSource
    timestamp: datetime = field(default_factory=datetime.now)
    checksum: str = ""
    version: str = "1.0"


@dataclass
class SyncMetadata:
    """同步元数据"""
    project_id: str
    form_id: str
    total_chunks: int
    chunk_ids: List[str]
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    last_modified: datetime = field(default_factory=datetime.now)


@dataclass
class SyncResult:
    """同步结果"""
    success: bool
    project_id: str
    form_id: str
    chunks_stored: int
    total_nodes: int
    timestamp: datetime = field(default_factory=datetime.now)
    error: str = ""


# ==================== 数据加密器 ====================

class DataEncryptor:
    """数据加密器（简化版，实际应使用更强的加密）"""

    @staticmethod
    def encrypt(data: Dict, key: str = None) -> Dict:
        """
        简单加密数据

        Args:
            data: 待加密数据
            key: 加密密钥（可选）

        Returns:
            Dict: 加密后的数据
        """
        # 简化实现：仅做哈希校验，实际应使用AES等强加密
        data_str = json.dumps(data, ensure_ascii=False, sort_keys=True)
        checksum = hashlib.sha256(data_str.encode()).hexdigest()

        return {
            "_encrypted": True,
            "_checksum": checksum,
            "_data": data,  # 简化：未实际加密
            "_timestamp": datetime.now().isoformat()
        }

    @staticmethod
    def decrypt(encrypted_data: Dict, key: str = None) -> Dict:
        """
        解密数据

        Args:
            encrypted_data: 加密数据
            key: 解密密钥

        Returns:
            Dict: 解密后的数据
        """
        # 验证校验和
        stored_checksum = encrypted_data.get("_checksum", "")
        data_str = json.dumps(
            encrypted_data["_data"],
            ensure_ascii=False,
            sort_keys=True
        )
        computed_checksum = hashlib.sha256(data_str.encode()).hexdigest()

        if stored_checksum != computed_checksum:
            raise ValueError("数据校验失败，可能已被篡改")

        return encrypted_data["_data"]

    @staticmethod
    def generate_checksum(data: Dict) -> str:
        """生成数据校验和"""
        data_str = json.dumps(data, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()


# ==================== P2P存储接口 ====================

class P2PStorageInterface:
    """P2P存储接口（对接现有P2P网络）"""

    def __init__(self, p2p_network=None):
        """
        Args:
            p2p_network: P2P网络实例
        """
        self.network = p2p_network
        self._use_mock = p2p_network is None

    async def store_chunk(
        self,
        chunk_id: str,
        data: Dict,
        ttl_days: int = 30
    ) -> bool:
        """
        存储数据块

        Args:
            chunk_id: 数据块ID
            data: 数据
            ttl_days: 存活时间（天）

        Returns:
            bool: 是否成功
        """
        if self._use_mock:
            return await self._mock_store(chunk_id, data)

        # 调用实际P2P网络存储
        encrypted = DataEncryptor.encrypt(data)
        return await self.network.store(
            key=chunk_id,
            value=encrypted,
            ttl=ttl_days * 24 * 3600
        )

    async def retrieve_chunk(self, chunk_id: str) -> Optional[Dict]:
        """
        获取数据块

        Args:
            chunk_id: 数据块ID

        Returns:
            Optional[Dict]: 数据
        """
        if self._use_mock:
            return await self._mock_retrieve(chunk_id)

        # 调用实际P2P网络获取
        encrypted = await self.network.retrieve(chunk_id)
        if encrypted:
            return DataEncryptor.decrypt(encrypted)
        return None

    async def _mock_store(self, chunk_id: str, data: Dict) -> bool:
        """模拟存储"""
        await asyncio.sleep(0.01)
        return True

    async def _mock_retrieve(self, chunk_id: str) -> Optional[Dict]:
        """模拟获取"""
        await asyncio.sleep(0.01)
        return None


# ==================== 表单数据同步器 ====================

class FormDataSynchronizer:
    """
    表单数据同步器

    核心功能：
    1. 将表单数据分块存储到P2P网络
    2. 支持多版本和变更追踪
    3. 冲突检测与解决
    4. 数据完整性校验
    """

    # 分块大小阈值
    CHUNK_SIZE_THRESHOLD = 1024 * 10  # 10KB

    def __init__(self, p2p_network=None):
        """
        Args:
            p2p_network: P2P网络实例
        """
        self.p2p_storage = P2PStorageInterface(p2p_network)
        self.encryptor = DataEncryptor()

        # 本地缓存
        self._local_cache: Dict[str, Dict] = {}
        self._metadata_cache: Dict[str, SyncMetadata] = {}

        # 版本历史
        self._version_history: Dict[str, List[Dict]] = {}

    async def save_form_data(
        self,
        project_id: str,
        form_id: str,
        form_data: Dict,
        source: DataSource = DataSource.OWNER_INPUT,
        metadata: Dict = None
    ) -> SyncResult:
        """
        保存表单数据到P2P网络

        Args:
            project_id: 项目ID
            form_id: 表单ID
            form_data: 表单数据
            source: 数据来源
            metadata: 附加元数据

        Returns:
            SyncResult: 同步结果
        """
        try:
            # 1. 记录版本历史
            self._record_version(project_id, form_id, form_data)

            # 2. 添加数据来源标记
            enriched_data = {
                "_meta": {
                    "project_id": project_id,
                    "form_id": form_id,
                    "source": source.value,
                    "timestamp": datetime.now().isoformat(),
                    "version": len(self._version_history.get(form_id, [])),
                    **(metadata or {})
                },
                "_fields": form_data
            }

            # 3. 分块
            chunks = self._split_into_chunks(form_id, enriched_data)

            # 4. 存储到多个节点
            storage_nodes = await self._get_storage_nodes(3)
            stored_count = 0

            for chunk in chunks:
                success = await self.p2p_storage.store_chunk(
                    chunk.chunk_id,
                    chunk.data
                )
                if success:
                    stored_count += 1

            # 5. 存储元数据
            sync_metadata = SyncMetadata(
                project_id=project_id,
                form_id=form_id,
                total_chunks=len(chunks),
                chunk_ids=[c.chunk_id for c in chunks],
                source=source.value
            )
            await self._save_metadata(sync_metadata)

            return SyncResult(
                success=True,
                project_id=project_id,
                form_id=form_id,
                chunks_stored=stored_count,
                total_nodes=len(storage_nodes)
            )

        except Exception as e:
            return SyncResult(
                success=False,
                project_id=project_id,
                form_id=form_id,
                chunks_stored=0,
                total_nodes=0,
                error=str(e)
            )

    async def load_form_data(
        self,
        project_id: str,
        form_id: str,
        version: int = None
    ) -> Optional[Dict]:
        """
        加载表单数据

        Args:
            project_id: 项目ID
            form_id: 表单ID
            version: 指定版本（None为最新）

        Returns:
            Optional[Dict]: 表单数据
        """
        # 如果指定版本，从历史加载
        if version is not None:
            history = self._version_history.get(form_id, [])
            if 0 <= version < len(history):
                return history[version]["data"]["_fields"]
            return None

        # 否则从P2P网络加载
        metadata = await self._load_metadata(form_id)
        if not metadata:
            return None

        # 重组数据块
        chunks_data = []
        for chunk_id in metadata.chunk_ids:
            chunk_data = await self.p2p_storage.retrieve_chunk(chunk_id)
            if chunk_data:
                chunks_data.append(chunk_data)

        if not chunks_data:
            return None

        # 合并数据块
        full_data = self._merge_chunks(chunks_data)
        return full_data.get("_fields")

    async def get_form_versions(self, form_id: str) -> List[Dict]:
        """
        获取表单版本历史

        Args:
            form_id: 表单ID

        Returns:
            List[Dict]: 版本历史列表
        """
        history = self._version_history.get(form_id, [])
        return [
            {
                "version": i,
                "timestamp": v["timestamp"],
                "source": v["data"]["_meta"].get("source", "unknown")
            }
            for i, v in enumerate(history)
        ]

    async def diff_versions(
        self,
        form_id: str,
        version1: int,
        version2: int
    ) -> Dict:
        """
        比较两个版本的差异

        Args:
            form_id: 表单ID
            version1: 版本1
            version2: 版本2

        Returns:
            Dict: 差异报告
        """
        history = self._version_history.get(form_id, [])

        if version1 >= len(history) or version2 >= len(history):
            return {"error": "版本不存在"}

        data1 = history[version1]["data"].get("_fields", {})
        data2 = history[version2]["data"].get("_fields", {})

        diff = {
            "added": {},
            "removed": {},
            "modified": {}
        }

        # 找出新增字段
        for k, v in data2.items():
            if k not in data1:
                diff["added"][k] = v

        # 找出删除字段
        for k, v in data1.items():
            if k not in data2:
                diff["removed"][k] = v

        # 找出修改字段
        for k, v in data1.items():
            if k in data2 and v != data2[k]:
                diff["modified"][k] = {
                    "old": v,
                    "new": data2[k]
                }

        return diff

    def _record_version(
        self,
        project_id: str,
        form_id: str,
        form_data: Dict
    ):
        """记录版本"""
        if form_id not in self._version_history:
            self._version_history[form_id] = []

        self._version_history[form_id].append({
            "project_id": project_id,
            "data": {
                "_meta": {
                    "project_id": project_id,
                    "form_id": form_id,
                    "timestamp": datetime.now().isoformat()
                },
                "_fields": copy.deepcopy(form_data)
            },
            "timestamp": datetime.now()
        })

        # 限制历史记录数量
        if len(self._version_history[form_id]) > 50:
            self._version_history[form_id] = self._version_history[form_id][-50:]

    def _split_into_chunks(
        self,
        form_id: str,
        data: Dict
    ) -> List[FormDataChunk]:
        """
        将数据分块

        Args:
            form_id: 表单ID
            data: 数据

        Returns:
            List[FormDataChunk]: 数据块列表
        """
        chunks = []

        # 元数据块
        meta_chunk = FormDataChunk(
            chunk_id=f"{form_id}_meta_v{len(self._version_history.get(form_id, []))}",
            data=data["_meta"],
            source=DataSource.AI_EXTRACT,
            checksum=self.encryptor.generate_checksum(data["_meta"])
        )
        chunks.append(meta_chunk)

        # 字段数据块
        fields = data["_fields"]
        field_chunks = []

        # 按类别分组
        categories = {}
        for field_name, field_value in fields.items():
            cat = "other"
            # 简化分类逻辑
            if field_name in ["project_name", "company_name", "contact_person"]:
                cat = "basic"
            elif field_name in ["emission_amount", "pollutant_name"]:
                cat = "technical"
            categories.setdefault(cat, {})[field_name] = field_value

        for cat, cat_data in categories.items():
            chunk = FormDataChunk(
                chunk_id=f"{form_id}_{cat}_v{len(self._version_history.get(form_id, []))}",
                data=cat_data,
                source=DataSource.OWNER_INPUT,
                checksum=self.encryptor.generate_checksum(cat_data)
            )
            chunks.append(chunk)

        return chunks

    def _merge_chunks(self, chunks_data: List[Dict]) -> Dict:
        """合并数据块"""
        merged = {}

        for chunk in chunks_data:
            if "_meta" in chunk:
                merged["_meta"] = chunk["_meta"]
            else:
                merged.update(chunk)

        return merged

    async def _get_storage_nodes(self, count: int) -> List[str]:
        """获取存储节点"""
        # 简化实现
        return [f"node_{i}" for i in range(count)]

    async def _save_metadata(self, metadata: SyncMetadata):
        """保存元数据"""
        self._metadata_cache[metadata.form_id] = metadata

    async def _load_metadata(self, form_id: str) -> Optional[SyncMetadata]:
        """加载元数据"""
        return self._metadata_cache.get(form_id)


# ==================== 表单变更追踪器 ====================

class FormChangeTracker:
    """表单变更追踪器"""

    def __init__(self):
        self._changes: Dict[str, List[Dict]] = {}

    def track_change(
        self,
        form_id: str,
        field_name: str,
        old_value: Any,
        new_value: Any,
        change_type: str = "modify"
    ) -> str:
        """
        追踪变更

        Args:
            form_id: 表单ID
            field_name: 字段名
            old_value: 旧值
            new_value: 新值
            change_type: 变更类型 (create/modify/delete)

        Returns:
            str: 变更ID
        """
        if form_id not in self._changes:
            self._changes[form_id] = []

        change_id = hashlib.md5(
            f"{form_id}_{field_name}_{time.time()}".encode()
        ).hexdigest()[:12]

        change = {
            "change_id": change_id,
            "field_name": field_name,
            "old_value": old_value,
            "new_value": new_value,
            "change_type": change_type,
            "timestamp": datetime.now().isoformat()
        }

        self._changes[form_id].append(change)

        return change_id

    def get_changes(self, form_id: str) -> List[Dict]:
        """获取表单的所有变更"""
        return self._changes.get(form_id, [])

    def get_field_changes(
        self,
        form_id: str,
        field_name: str
    ) -> List[Dict]:
        """获取特定字段的变更历史"""
        changes = self._changes.get(form_id, [])
        return [c for c in changes if c["field_name"] == field_name]

    def generate_change_report(self, form_id: str) -> Dict:
        """生成变更报告"""
        changes = self.get_changes(form_id)

        return {
            "form_id": form_id,
            "total_changes": len(changes),
            "change_summary": {
                "created": len([c for c in changes if c["change_type"] == "create"]),
                "modified": len([c for c in changes if c["change_type"] == "modify"]),
                "deleted": len([c for c in changes if c["change_type"] == "delete"]),
            },
            "recent_changes": changes[-10:] if len(changes) > 10 else changes
        }


# ==================== 导出 ====================

_synchronizer_instance: Optional[FormDataSynchronizer] = None
_tracker_instance: Optional[FormChangeTracker] = None


def get_synchronizer() -> FormDataSynchronizer:
    """获取数据同步器单例"""
    global _synchronizer_instance
    if _synchronizer_instance is None:
        _synchronizer_instance = FormDataSynchronizer()
    return _synchronizer_instance


def get_tracker() -> FormChangeTracker:
    """获取变更追踪器单例"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = FormChangeTracker()
    return _tracker_instance


async def save_form_data_async(
    project_id: str,
    form_id: str,
    form_data: Dict,
    source: str = "owner_input"
) -> SyncResult:
    """
    异步保存表单数据的便捷函数

    Args:
        project_id: 项目ID
        form_id: 表单ID
        form_data: 表单数据
        source: 数据来源

    Returns:
        SyncResult: 同步结果
    """
    synchronizer = get_synchronizer()
    return await synchronizer.save_form_data(
        project_id,
        form_id,
        form_data,
        DataSource(source)
    )


async def load_form_data_async(
    project_id: str,
    form_id: str
) -> Optional[Dict]:
    """
    异步加载表单数据的便捷函数

    Args:
        project_id: 项目ID
        form_id: 表单ID

    Returns:
        Optional[Dict]: 表单数据
    """
    synchronizer = get_synchronizer()
    return await synchronizer.load_form_data(project_id, form_id)
