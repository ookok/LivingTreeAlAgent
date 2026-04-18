# =================================================================
# 可溯源节点 - Traceable Node
# =================================================================
# 功能：
# 1. 可溯源节点的基类
# 2. 版本管理和追溯
# 3. 溯源链构建
# =================================================================

import json
import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .content_hasher import ContentHasher, HashResult, HashType
from .event_logger import EventLogger, EventType, EntityType


class NodeType(Enum):
    """节点类型"""
    KNOWLEDGE = "knowledge"       # 知识节点
    PRODUCT = "product"          # 商品节点
    SERVICE = "service"         # 服务节点
    DOCUMENT = "document"       # 文档节点
    CHUNK = "chunk"            # 内容块节点
    ASSEMBLY = "assembly"      # 装配节点
    FILE = "file"              # 文件节点


@dataclass
class NodeVersion:
    """节点版本"""
    version_id: str
    version_number: int

    # 内容哈希
    content_hash: str
    algorithm: str = "sha256"

    # 时间
    created_at: float = field(default_factory=time.time)
    created_by: str = "system"

    # 版本信息
    changelog: str = ""
    previous_version_id: str = ""

    @property
    def created_at_str(self) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(self.created_at).isoformat()


@dataclass
class Source:
    """来源信息"""
    source_id: str
    source_type: str              # url / file / entity / user
    source_url: str = ""
    source_file: str = ""
    source_entity_id: str = ""
    relation: str = "derived_from"  # derived_from / cited_by / input_of

    # 引用位置（用于文档）
    location: str = ""           # "page 3", "section 2.1"
    excerpt: str = ""           # 引用片段

    @property
    def display_text(self) -> str:
        if self.source_url:
            return f"📌 来源: {self.source_url}"
        elif self.source_file:
            return f"📄 来源: {self.source_file}"
        elif self.source_entity_id:
            return f"🔗 来源: {self.source_entity_id}"
        return f"📌 来源: {self.source_id}"


@dataclass
class TraceableNode:
    """
    可溯源节点基类

    核心特性：
    1. 唯一标识符
    2. 版本管理
    3. 溯源链
    4. 内容指纹
    """

    # 基础信息
    node_id: str
    node_type: NodeType
    name: str
    description: str = ""

    # 内容
    content: str = ""            # 主要内容
    content_type: str = "text"    # text/html/markdown/file

    # 文件路径（如果是文件节点）
    file_path: str = ""

    # 版本信息
    version_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    version_number: int = 1
    versions: List[NodeVersion] = field(default_factory=list)

    # 溯源信息
    sources: List[Source] = field(default_factory=list)
    derived_nodes: List[str] = field(default_factory=list)  # 派生出的节点ID

    # 哈希
    content_hash: str = ""
    hash_algorithm: HashType = HashType.SHA256

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 标签
    tags: List[str] = field(default_factory=list)

    # 状态
    is_active: bool = True
    is_deleted: bool = False

    # 时间戳
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # 创建者
    created_by: str = "system"
    owner: str = "system"

    def __post_init__(self):
        if not self.node_id:
            self.node_id = str(uuid.uuid4())[:12]

        # 计算内容哈希
        if self.content and not self.content_hash:
            hasher = ContentHasher()
            result = hasher.hash_string(self.content, self.hash_algorithm)
            self.content_hash = result.hash_value

    @property
    def node_id_short(self) -> str:
        """短ID（8位）"""
        return self.node_id[:8]

    @property
    def created_at_str(self) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(self.created_at).isoformat()

    @property
    def updated_at_str(self) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(self.updated_at).isoformat()

    # ========== 版本管理 ==========

    def create_version(
        self,
        new_content: str,
        changelog: str = "",
        created_by: str = "system"
    ) -> NodeVersion:
        """
        创建新版本

        Args:
            new_content: 新内容
            changelog: 变更说明
            created_by: 创建者

        Returns:
            新版本
        """
        # 计算新内容的哈希
        hasher = ContentHasher()
        result = hasher.hash_string(new_content, self.hash_algorithm)

        # 如果内容没变，不创建新版本
        if result.hash_value == self.content_hash:
            return self.versions[-1] if self.versions else None

        # 创建新版本
        new_version = NodeVersion(
            version_id=str(uuid.uuid4())[:12],
            version_number=self.version_number + 1,
            content_hash=result.hash_value,
            algorithm=self.hash_algorithm.value,
            created_by=created_by,
            changelog=changelog,
            previous_version_id=self.version_id
        )

        # 更新节点
        self.versions.append(new_version)
        self.version_id = new_version.version_id
        self.version_number = new_version.version_number
        self.content_hash = result.hash_value
        self.content = new_content
        self.updated_at = time.time()

        return new_version

    def get_version(self, version_number: int) -> Optional[NodeVersion]:
        """获取指定版本"""
        for v in self.versions:
            if v.version_number == version_number:
                return v
        return None

    def get_latest_version(self) -> Optional[NodeVersion]:
        """获取最新版本"""
        return self.versions[-1] if self.versions else None

    def get_version_history(self) -> List[NodeVersion]:
        """获取版本历史（倒序）"""
        return self.versions[::-1]

    # ========== 溯源链 ==========

    def add_source(
        self,
        source_type: str,
        source_id: str,
        relation: str = "derived_from",
        source_url: str = "",
        source_file: str = "",
        location: str = "",
        excerpt: str = ""
    ) -> Source:
        """
        添加来源

        Args:
            source_type: 来源类型 (url/file/entity/user)
            source_id: 来源ID
            relation: 关系
            source_url: 来源URL
            source_file: 来源文件
            location: 引用位置
            excerpt: 引用片段

        Returns:
            创建的来源
        """
        source = Source(
            source_id=source_id,
            source_type=source_type,
            source_url=source_url,
            source_file=source_file,
            relation=relation,
            location=location,
            excerpt=excerpt
        )
        self.sources.append(source)
        self.updated_at = time.time()
        return source

    def add_url_source(
        self,
        url: str,
        title: str = "",
        location: str = "",
        excerpt: str = ""
    ) -> Source:
        """添加 URL 来源"""
        import hashlib
        source_id = hashlib.md5(url.encode()).hexdigest()[:12]
        return self.add_source(
            source_type="url",
            source_id=source_id,
            source_url=url,
            relation="cited_from",
            location=location,
            excerpt=excerpt
        )

    def add_file_source(
        self,
        file_path: str,
        location: str = "",
        excerpt: str = ""
    ) -> Source:
        """添加文件来源"""
        import hashlib
        source_id = hashlib.md5(file_path.encode()).hexdigest()[:12]
        return self.add_source(
            source_type="file",
            source_id=source_id,
            source_file=file_path,
            relation="extracted_from",
            location=location,
            excerpt=excerpt
        )

    def add_entity_source(
        self,
        entity_id: str,
        entity_type: str,
        relation: str = "derived_from"
    ) -> Source:
        """添加实体来源"""
        return self.add_source(
            source_type="entity",
            source_id=entity_id,
            source_entity_id=entity_id,
            relation=relation
        )

    def get_provenance_chain(self) -> List[Dict[str, Any]]:
        """
        获取溯源链

        Returns:
            从源头到当前节点的完整链路
        """
        chain = []
        current = self

        while current:
            chain.append({
                "node_id": current.node_id,
                "node_type": current.node_type.value,
                "name": current.name,
                "version_number": current.version_number,
                "content_hash": current.content_hash,
                "created_at": current.created_at_str,
                "sources_count": len(current.sources),
                "sources": [
                    {
                        "type": s.source_type,
                        "id": s.source_id,
                        "relation": s.relation,
                        "display": s.display_text
                    }
                    for s in current.sources
                ]
            })

            # 找到上一个来源（简化处理：只取第一个实体来源）
            next_source = None
            for source in current.sources:
                if source.source_type == "entity":
                    next_source = source
                    break

            if next_source:
                # 这里需要外部图谱查询来获取完整链
                break
            else:
                break

        return chain

    # ========== 标签 ==========

    def add_tag(self, tag: str):
        """添加标签"""
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = time.time()

    def remove_tag(self, tag: str):
        """移除标签"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = time.time()

    def has_tag(self, tag: str) -> bool:
        """检查标签"""
        return tag in self.tags

    # ========== 序列化 ==========

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "content_type": self.content_type,
            "file_path": self.file_path,
            "version_id": self.version_id,
            "version_number": self.version_number,
            "versions": [
                {
                    "version_id": v.version_id,
                    "version_number": v.version_number,
                    "content_hash": v.content_hash,
                    "algorithm": v.algorithm,
                    "created_at": v.created_at_str,
                    "created_by": v.created_by,
                    "changelog": v.changelog
                }
                for v in self.versions
            ],
            "sources": [
                {
                    "source_id": s.source_id,
                    "source_type": s.source_type,
                    "source_url": s.source_url,
                    "source_file": s.source_file,
                    "source_entity_id": s.source_entity_id,
                    "relation": s.relation,
                    "location": s.location,
                    "excerpt": s.excerpt
                }
                for s in self.sources
            ],
            "derived_nodes": self.derived_nodes,
            "content_hash": self.content_hash,
            "hash_algorithm": self.hash_algorithm.value,
            "metadata": self.metadata,
            "tags": self.tags,
            "is_active": self.is_active,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at_str,
            "updated_at": self.updated_at_str,
            "created_by": self.created_by,
            "owner": self.owner
        }

    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TraceableNode':
        """从字典创建"""
        # 处理 NodeType
        node_type = NodeType(data.get("node_type", "knowledge"))

        # 处理 HashType
        hash_algo = HashType(data.get("hash_algorithm", "sha256"))

        # 处理版本
        versions = [
            NodeVersion(
                version_id=v["version_id"],
                version_number=v["version_number"],
                content_hash=v["content_hash"],
                algorithm=v.get("algorithm", "sha256"),
                created_at=v.get("created_at", time.time()),
                created_by=v.get("created_by", "system"),
                changelog=v.get("changelog", ""),
                previous_version_id=v.get("previous_version_id", "")
            )
            for v in data.get("versions", [])
        ]

        # 处理来源
        sources = [
            Source(
                source_id=s["source_id"],
                source_type=s.get("source_type", "unknown"),
                source_url=s.get("source_url", ""),
                source_file=s.get("source_file", ""),
                source_entity_id=s.get("source_entity_id", ""),
                relation=s.get("relation", "derived_from"),
                location=s.get("location", ""),
                excerpt=s.get("excerpt", "")
            )
            for s in data.get("sources", [])
        ]

        return cls(
            node_id=data.get("node_id", str(uuid.uuid4())[:12]),
            node_type=node_type,
            name=data.get("name", ""),
            description=data.get("description", ""),
            content=data.get("content", ""),
            content_type=data.get("content_type", "text"),
            file_path=data.get("file_path", ""),
            version_id=data.get("version_id", str(uuid.uuid4())[:12]),
            version_number=data.get("version_number", 1),
            versions=versions,
            sources=sources,
            derived_nodes=data.get("derived_nodes", []),
            content_hash=data.get("content_hash", ""),
            hash_algorithm=hash_algo,
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            is_active=data.get("is_active", True),
            is_deleted=data.get("is_deleted", False),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            created_by=data.get("created_by", "system"),
            owner=data.get("owner", "system")
        )

    @classmethod
    def from_json(cls, json_str: str) -> 'TraceableNode':
        """从 JSON 字符串创建"""
        return cls.from_dict(json.loads(json_str))


@dataclass
class ProvenanceChain:
    """
    溯源链

    存储从源头到终点的完整链路
    """
    chain_id: str
    chain_type: str              # knowledge / product / service

    # 链路节点
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    # [{node_id, node_type, name, relation, version}]

    # 元数据
    start_node_id: str = ""
    end_node_id: str = ""
    chain_length: int = 0

    created_at: float = field(default_factory=time.time)

    def add_node(
        self,
        node_id: str,
        node_type: str,
        name: str,
        relation: str = "",
        version: int = 1
    ):
        """添加节点到链路"""
        self.nodes.append({
            "node_id": node_id,
            "node_type": node_type,
            "name": name,
            "relation": relation,
            "version": version
        })
        self.chain_length = len(self.nodes)

    def to_list(self) -> List[Dict[str, Any]]:
        """转换为列表"""
        return self.nodes

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        lines = [f"# 溯源链: {self.chain_id}", ""]
        lines.append(f"**类型**: {self.chain_type}")
        lines.append(f"**长度**: {self.chain_length}")
        lines.append("")

        for i, node in enumerate(self.nodes):
            prefix = "→" if i > 0 else "●"
            lines.append(f"{prefix} **{node['name']}**")
            lines.append(f"   - ID: `{node['node_id']}`")
            lines.append(f"   - 类型: {node['node_type']}")
            if node.get('relation'):
                lines.append(f"   - 关系: {node['relation']}")
            lines.append("")

        return "\n".join(lines)


# ========== 便捷函数 ==========

def create_traceable_node(
    node_type: NodeType,
    name: str,
    content: str = "",
    sources: List[Dict] = None,
    tags: List[str] = None,
    metadata: Dict = None,
    created_by: str = "system"
) -> TraceableNode:
    """
    创建可溯源节点

    便捷函数
    """
    node = TraceableNode(
        node_id=str(uuid.uuid4())[:12],
        node_type=node_type,
        name=name,
        content=content,
        created_by=created_by
    )

    if sources:
        for source in sources:
            if isinstance(source, dict):
                node.add_source(**source)
            elif isinstance(source, Source):
                node.sources.append(source)

    if tags:
        node.tags.extend(tags)

    if metadata:
        node.metadata.update(metadata)

    return node
