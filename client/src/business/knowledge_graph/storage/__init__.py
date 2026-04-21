"""
知识存储层 - 混合存储架构
============================

提供三层存储接口：
1. 图数据库存储 (GraphStorage) - Neo4j/Nebula兼容
2. 向量数据库存储 (VectorStorage) - Chroma/Weaviate兼容
3. 对象存储 (ObjectStorage) - MinIO/S3兼容

Author: Hermes Desktop Team
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json
import os

from . import KnowledgeGraph, Entity, Relation, EntityType, RelationType


# ============================================================
# 第一部分：配置类
# ============================================================

@dataclass
class StorageConfig:
    """存储配置"""
    graph_db_type: str = "memory"
    graph_host: str = "localhost"
    graph_port: int = 7687
    graph_user: str = "neo4j"
    graph_password: str = ""

    vector_db_type: str = "memory"
    vector_host: str = "localhost"
    vector_port: int = 8000
    vector_collection: str = "knowledge"

    object_storage_type: str = "local"
    object_storage_path: str = "./data/knowledge/objects"
    object_storage_endpoint: str = ""
    object_storage_access_key: str = ""
    object_storage_secret_key: str = ""

    cache_enabled: bool = True
    cache_size: int = 1000


# ============================================================
# 第二部分：向量条目
# ============================================================

@dataclass
class VectorEntry:
    """向量条目"""
    id: str
    vector: List[float]
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    entity_id: Optional[str] = None


# ============================================================
# 第三部分：图数据库存储
# ============================================================

class GraphStorageInterface(ABC):
    """图数据库存储接口"""

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def create_indexes(self) -> None:
        pass

    @abstractmethod
    def insert_entity(self, entity: Entity) -> bool:
        pass

    @abstractmethod
    def insert_relation(self, relation: Relation) -> bool:
        pass

    @abstractmethod
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        pass

    @abstractmethod
    def get_entities_by_type(self, entity_type: EntityType) -> List[Entity]:
        pass

    @abstractmethod
    def query(self, cypher: str) -> List[Dict]:
        pass

    @abstractmethod
    def delete_entity(self, entity_id: str) -> bool:
        pass

    @abstractmethod
    def batch_insert(self, kg: KnowledgeGraph) -> int:
        pass


class MemoryGraphStorage(GraphStorageInterface):
    """内存图数据库"""

    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self._entities: Dict[str, Entity] = {}
        self._relations: Dict[str, Relation] = {}
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def create_indexes(self) -> None:
        pass

    def insert_entity(self, entity: Entity) -> bool:
        if not self._connected:
            return False
        self._entities[entity.id] = entity
        return True

    def insert_relation(self, relation: Relation) -> bool:
        if not self._connected:
            return False
        self._relations[relation.id] = relation
        return True

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)

    def get_entities_by_type(self, entity_type: EntityType) -> List[Entity]:
        return [e for e in self._entities.values() if e.entity_type == entity_type]

    def query(self, cypher: str) -> List[Dict]:
        results = []
        if "MATCH" in cypher.upper() and "Process" in cypher:
            for entity in self._entities.values():
                if entity.entity_type == EntityType.PROCESS:
                    results.append(entity.to_dict())
        return results

    def delete_entity(self, entity_id: str) -> bool:
        if entity_id in self._entities:
            del self._entities[entity_id]
            return True
        return False

    def batch_insert(self, kg: KnowledgeGraph) -> int:
        count = 0
        for entity in kg.entities.values():
            if self.insert_entity(entity):
                count += 1
        for relation in kg.relations.values():
            if self.insert_relation(relation):
                count += 1
        return count


# ============================================================
# 第四部分：向量数据库存储
# ============================================================

class VectorStorageInterface(ABC):
    """向量数据库存储接口"""

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def create_collection(self, name: str, dimension: int) -> bool:
        pass

    @abstractmethod
    def insert_vector(self, entry: VectorEntry) -> bool:
        pass

    @abstractmethod
    def search(self, query_vector: List[float], top_k: int = 10,
               filter_metadata: Optional[Dict] = None) -> List[Tuple[VectorEntry, float]]:
        pass

    @abstractmethod
    def search_by_text(self, text: str, top_k: int = 10,
                       filter_metadata: Optional[Dict] = None) -> List[Tuple[VectorEntry, float]]:
        pass


class MemoryVectorStorage(VectorStorageInterface):
    """内存向量存储"""

    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self._vectors: Dict[str, VectorEntry] = {}
        self._dimension = 0
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def create_collection(self, name: str, dimension: int) -> bool:
        if not self._connected:
            return False
        self._dimension = dimension
        return True

    def insert_vector(self, entry: VectorEntry) -> bool:
        if not self._connected:
            return False
        self._vectors[entry.id] = entry
        return True

    def _compute_text_similarity(self, text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union) if union else 0.0

    def search(self, query_vector: List[float], top_k: int = 10,
               filter_metadata: Optional[Dict] = None) -> List[Tuple[VectorEntry, float]]:
        results = []
        for entry in self._vectors.values():
            if filter_metadata:
                match = all(entry.metadata.get(k) == v for k, v in filter_metadata.items())
                if not match:
                    continue
            score = self._compute_text_similarity(str(query_vector), entry.text)
            results.append((entry, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def search_by_text(self, text: str, top_k: int = 10,
                       filter_metadata: Optional[Dict] = None) -> List[Tuple[VectorEntry, float]]:
        results = []
        for entry in self._vectors.values():
            if filter_metadata:
                match = all(entry.metadata.get(k) == v for k, v in filter_metadata.items())
                if not match:
                    continue
            score = self._compute_text_similarity(text, entry.text)
            if score > 0:
                results.append((entry, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


# ============================================================
# 第五部分：对象存储
# ============================================================

class ObjectStorageInterface(ABC):
    """对象存储接口"""

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        pass

    @abstractmethod
    def download(self, key: str) -> Optional[bytes]:
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        pass

    @abstractmethod
    def list(self, prefix: str = "") -> List[str]:
        pass


class LocalObjectStorage(ObjectStorageInterface):
    """本地文件系统存储"""

    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self._base_path = self.config.object_storage_path
        self._connected = False

    def connect(self) -> bool:
        os.makedirs(self._base_path, exist_ok=True)
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def _get_full_path(self, key: str) -> str:
        return os.path.join(self._base_path, key)

    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        if not self._connected:
            return False
        try:
            full_path = self._get_full_path(key)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'wb') as f:
                f.write(data)
            return True
        except Exception as e:
            print(f"上传失败: {e}")
            return False

    def download(self, key: str) -> Optional[bytes]:
        if not self._connected:
            return None
        try:
            full_path = self._get_full_path(key)
            with open(full_path, 'rb') as f:
                return f.read()
        except Exception:
            return None

    def delete(self, key: str) -> bool:
        if not self._connected:
            return False
        try:
            full_path = self._get_full_path(key)
            if os.path.exists(full_path):
                os.remove(full_path)
            return True
        except Exception:
            return False

    def list(self, prefix: str = "") -> List[str]:
        if not self._connected:
            return []
        try:
            full_prefix = self._get_full_path(prefix)
            if os.path.exists(full_prefix):
                return os.listdir(full_prefix)
            return []
        except Exception:
            return []


# ============================================================
# 第六部分：混合存储管理器
# ============================================================

class HybridStorageManager:
    """混合存储管理器"""

    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self.graph_storage: Optional[GraphStorageInterface] = None
        self.vector_storage: Optional[VectorStorageInterface] = None
        self.object_storage: Optional[ObjectStorageInterface] = None
        self._init_storages()

    def _init_storages(self) -> None:
        self.graph_storage = MemoryGraphStorage(self.config)
        self.vector_storage = MemoryVectorStorage(self.config)
        self.object_storage = LocalObjectStorage(self.config)

    def connect_all(self) -> Dict[str, bool]:
        results = {}
        if self.graph_storage:
            results['graph'] = self.graph_storage.connect()
        if self.vector_storage:
            results['vector'] = self.vector_storage.connect()
        if self.object_storage:
            results['object'] = self.object_storage.connect()
        return results

    def disconnect_all(self) -> None:
        if self.graph_storage:
            self.graph_storage.disconnect()
        if self.vector_storage:
            self.vector_storage.disconnect()
        if self.object_storage:
            self.object_storage.disconnect()

    def store_knowledge_graph(self, kg: KnowledgeGraph) -> bool:
        if not self.graph_storage:
            return False
        try:
            self.graph_storage.batch_insert(kg)
            if self.vector_storage:
                self.vector_storage.create_collection(self.config.vector_collection, 384)
                for entity in kg.entities.values():
                    import random
                    vector = [random.random() for _ in range(384)]
                    text = self._entity_to_text(entity)
                    entry = VectorEntry(
                        id=entity.id,
                        vector=vector,
                        text=text,
                        metadata={"entity_type": entity.entity_type.value},
                        entity_id=entity.id
                    )
                    self.vector_storage.insert_vector(entry)
            return True
        except Exception as e:
            print(f"存储知识图谱失败: {e}")
            return False

    def _entity_to_text(self, entity: Entity) -> str:
        parts = [entity.name, entity.description]
        parts.extend(entity.aliases)
        for key, value in entity.properties.items():
            parts.append(f"{key}: {value}")
        return " ".join(str(p) for p in parts)

    def retrieve_similar(self, text: str, top_k: int = 10) -> List[Tuple[Entity, float]]:
        if not self.vector_storage or not self.graph_storage:
            return []
        results = self.vector_storage.search_by_text(text, top_k)
        entities = []
        for entry, score in results:
            entity = self.graph_storage.get_entity(entry.entity_id)
            if entity:
                entities.append((entity, score))
        return entities


# ============================================================
# 第七部分：缓存管理器
# ============================================================

class CacheManager:
    """缓存管理器"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: Dict[str, Any] = {}
        self._access_count: Dict[str, int] = {}
        self._last_access: Dict[str, datetime] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            self._access_count[key] = self._access_count.get(key, 0) + 1
            self._last_access[key] = datetime.now()
            return self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        if len(self._cache) >= self.max_size:
            self._evict()
        self._cache[key] = value
        self._access_count[key] = 1
        self._last_access[key] = datetime.now()

    def _evict(self) -> None:
        if not self._cache:
            return
        lru_key = min(self._last_access.items(), key=lambda x: x[1])[0]
        del self._cache[lru_key]
        del self._access_count[lru_key]
        del self._last_access[lru_key]

    def clear(self) -> None:
        self._cache.clear()
        self._access_count.clear()
        self._last_access.clear()


__all__ = [
    'StorageConfig', 'VectorEntry',
    'GraphStorageInterface', 'MemoryGraphStorage',
    'VectorStorageInterface', 'MemoryVectorStorage',
    'ObjectStorageInterface', 'LocalObjectStorage',
    'HybridStorageManager', 'CacheManager'
]
