"""
私有法规库向量数据库系统
Private Regulation Vector Database System

集成 Chroma / Milvus 向量数据库 + sentence-transformers 嵌入模型
实现本地化法规语义检索

核心优势:
1. Chroma - 轻量级、易部署、API简洁，适合中小规模（<100万向量）
2. Milvus - 高性能分布式、支持亿级向量、适合生产环境
3. all-MiniLM-L6-v2 - 80MB、超快推理、本地运行、无需API Key

适用场景:
- 企业内部法规检索
- 政策文件语义搜索
- 合规文档问答系统
- 知识库智能问答

Author: Hermes Desktop Team
"""

from core.logger import get_logger
logger = get_logger('regulation_vector_db')

import os
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path
from enum import Enum
import threading

# ============================================================
# 第一部分：向量数据库类型枚举
# ============================================================

class VectorDBType(Enum):
    """支持的向量数据库类型"""
    CHROMA = "chroma"
    MILVUS = "milvus"
    MEMORY = "memory"  # 仅开发测试用


class EmbeddingModelType(Enum):
    """支持的嵌入模型类型"""
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    TRANSFORMERS = "transformers"
    HUGGINGFACE_API = "huggingface_api"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"


# ============================================================
# 第二部分：配置类
# ============================================================

@dataclass
class VectorDBConfig:
    """向量数据库配置"""
    # 数据库类型
    db_type: VectorDBType = VectorDBType.CHROMA

    # Chroma 配置
    chroma_persist_directory: str = "./data/vector_db/chroma"
    chroma_collection_name: str = "regulations"

    # Milvus 配置
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection_name: str = "regulations"
    milvus_index_type: str = "IVF_FLAT"  # IVF_FLAT / HNSW / ANNOY
    milvus_metric_type: str = "L2"  # L2 / IP / COSINE

    # 集合配置
    collection_dimension: int = 384  # all-MiniLM-L6-v2 输出维度
    collection_distance_threshold: float = 1.0

    # 性能配置
    batch_size: int = 100
    max_connections: int = 100


@dataclass
class EmbeddingConfig:
    """嵌入模型配置"""
    model_type: EmbeddingModelType = EmbeddingModelType.SENTENCE_TRANSFORMERS

    # sentence-transformers 配置
    model_name: str = "all-MiniLM-L6-v2"  # 80MB, 384维, 速度快
    # 其他候选模型:
    # "BAAI/bge-small-zh-v1.5" - 中文优化, 384维
    # "BAAI/bge-base-zh-v1.5" - 中文优化, 768维
    # "shibing624/text2vec-base-chinese" - 中文模型, 768维
    # "moka-ai/m3e-base" - 中文模型, 768维

    device: str = "cpu"  # cpu / cuda
    normalize_embeddings: bool = True
    max_seq_length: int = 256

    # API 配置（备选）
    api_base_url: str = ""
    api_key: str = ""


@dataclass
class RegulationLaw:
    """法规条目"""
    law_id: str
    title: str
    content: str
    category: str = ""  # 法律法规/部门规章/规范性文件/司法解释
    department: str = ""  # 发布部门
    issue_date: str = ""  # 发布日期
    effective_date: str = ""  # 生效日期
    status: str = "有效"  # 有效/废止/修改
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "law_id": self.law_id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "department": self.department,
            "issue_date": self.issue_date,
            "effective_date": self.effective_date,
            "status": self.status,
            "keywords": self.keywords,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "RegulationLaw":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SearchResult:
    """检索结果"""
    law: RegulationLaw
    score: float  # 相似度分数
    highlight: str = ""  # 高亮片段
    rank: int = 0


# ============================================================
# 第三部分：嵌入模型接口
# ============================================================

class EmbeddingModel(ABC):
    """嵌入模型抽象接口"""

    @abstractmethod
    def encode(self, texts: Union[str, List[str]], **kwargs) -> List[List[float]]:
        """将文本编码为向量"""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """获取向量维度"""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """获取模型名称"""
        pass


class SentenceTransformersEmbedding(EmbeddingModel):
    """sentence-transformers 嵌入模型

    推荐使用 all-MiniLM-L6-v2:
    - 体积小: 80MB
    - 速度快: CPU上约 1400 sentences/s
    - 维度低: 384维，存储成本低
    - 性能足够: MTEB 基准测试表现优秀
    - 完全本地: 无需 API Key
    - 多语言: 支持中英文
    """

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._model = None
        self._dimension = config.collection_dimension

    def _load_model(self):
        """延迟加载模型"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(
                    self.config.model_name,
                    device=self.config.device
                )
                self._dimension = self._model.get_sentence_embedding_dimension()
                logger.info(f"[Embedding] 模型加载成功: {self.config.model_name}, 维度: {self._dimension}")
            except ImportError:
                logger.info("[Embedding] sentence-transformers 未安装，尝试使用替代方案...")
                raise

    def encode(self, texts: Union[str, List[str]], **kwargs) -> List[List[float]]:
        """编码文本为向量"""
        self._load_model()

        if isinstance(texts, str):
            texts = [texts]

        embeddings = self._model.encode(
            texts,
            batch_size=self.config.batch_size if hasattr(self, 'batch_size') else 32,
            show_progress_bar=False,
            normalize_embeddings=self.config.normalize_embeddings,
            convert_to_numpy=True,
            **kwargs
        )

        return embeddings.tolist()

    def get_dimension(self) -> int:
        """获取向量维度"""
        self._load_model()
        return self._dimension

    def get_model_name(self) -> str:
        return self.config.model_name


class TransformersEmbedding(EmbeddingModel):
    """HuggingFace Transformers 嵌入模型（备选）"""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._model = None
        self._tokenizer = None
        self._dimension = config.collection_dimension

    def _load_model(self):
        if self._model is None:
            from transformers import AutoTokenizer, AutoModel
            self._tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
            self._model = AutoModel.from_pretrained(self.config.model_name)
            self._model.eval()

    def encode(self, texts: Union[str, List[str]], **kwargs) -> List[List[float]]:
        self._load_model()

        if isinstance(texts, str):
            texts = [texts]

        embeddings = []
        for text in texts:
            inputs = self._tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=self.config.max_seq_length,
                padding=True
            )
            with torch.no_grad():
                outputs = self._model(**inputs)
                # Mean pooling
                embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
            embeddings.append(embedding.tolist())

        return embeddings

    def get_dimension(self) -> int:
        self._load_model()
        return self._dimension

    def get_model_name(self) -> str:
        return self.config.model_name


class MockEmbedding(EmbeddingModel):
    """模拟嵌入模型（用于测试）"""

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    def encode(self, texts: Union[str, List[str]], **kwargs) -> List[List[float]]:
        import random
        if isinstance(texts, str):
            texts = [texts]

        return [
            [random.random() for _ in range(self._dimension)]
            for _ in texts
        ]

    def get_dimension(self) -> int:
        return self._dimension

    def get_model_name(self) -> str:
        return "mock-embedding"


def create_embedding_model(config: EmbeddingConfig) -> EmbeddingModel:
    """创建嵌入模型实例"""
    if config.model_type == EmbeddingModelType.SENTENCE_TRANSFORMERS:
        return SentenceTransformersEmbedding(config)
    elif config.model_type == EmbeddingModelType.TRANSFORMERS:
        return TransformersEmbedding(config)
    elif config.model_type == EmbeddingModelType.MOCK:
        return MockEmbedding()
    else:
        raise ValueError(f"不支持的模型类型: {config.model_type}")


# ============================================================
# 第四部分：向量数据库接口
# ============================================================

class VectorDBInterface(ABC):
    """向量数据库抽象接口"""

    @abstractmethod
    def connect(self) -> bool:
        """连接数据库"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接"""
        pass

    @abstractmethod
    def create_collection(self, name: str, dimension: int) -> bool:
        """创建集合"""
        pass

    @abstractmethod
    def delete_collection(self, name: str) -> bool:
        """删除集合"""
        pass

    @abstractmethod
    def insert(self, ids: List[str], embeddings: List[List[float]],
               documents: List[str], metadatas: List[Dict]) -> bool:
        """插入向量"""
        pass

    @abstractmethod
    def search(self, query_vector: List[float], top_k: int = 10,
               filter_metadata: Optional[Dict] = None) -> List[Dict]:
        """向量检索"""
        pass

    @abstractmethod
    def search_by_text(self, text: str, top_k: int = 10,
                       filter_metadata: Optional[Dict] = None) -> List[Dict]:
        """文本检索"""
        pass

    @abstractmethod
    def delete(self, ids: List[str]) -> bool:
        """删除向量"""
        pass

    @abstractmethod
    def get_collection_info(self, name: str) -> Dict:
        """获取集合信息"""
        pass


class ChromaVectorDB(VectorDBInterface):
    """Chroma 向量数据库

    Chroma 优势:
    - 轻量级: Python 包，无额外依赖
    - 易部署: 一行命令启动 `chroma run`
    - API 简洁: 4 个核心函数 (add, query, get, delete)
    - 开发友好: 内置 HTTP 服务，支持多语言客户端
    - 持久化: 自动持久化到磁盘
    - 免费开源: Apache 2.0 许可

    适用规模:
    - 开发/测试环境
    - 小规模部署 (<100万向量)
    - 个人/小团队使用
    - 快速原型验证

    性能数据 (all-MiniLM-L6-v2, 384维):
    - 10万向量: ~100ms 查询
    - 100万向量: ~500ms 查询
    """

    def __init__(self, config: VectorDBConfig):
        self.config = config
        self._client = None
        self._collection = None

    def _get_client(self):
        """获取或创建客户端"""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings

                # 持久化客户端
                self._client = chromadb.PersistentClient(
                    path=self.config.chroma_persist_directory
                )
            except ImportError:
                logger.info("[ChromaDB] chromadb 未安装，执行: pip install chromadb")
                raise

        return self._client

    def connect(self) -> bool:
        try:
            self._get_client()
            return True
        except Exception as e:
            logger.info(f"[ChromaDB] 连接失败: {e}")
            return False

    def disconnect(self) -> None:
        self._client = None
        self._collection = None

    def create_collection(self, name: str, dimension: int) -> bool:
        try:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=name,
                metadata={"dimension": dimension}
            )
            return True
        except Exception as e:
            logger.info(f"[ChromaDB] 创建集合失败: {e}")
            return False

    def delete_collection(self, name: str) -> bool:
        try:
            client = self._get_client()
            client.delete_collection(name)
            return True
        except Exception as e:
            logger.info(f"[ChromaDB] 删除集合失败: {e}")
            return False

    def insert(self, ids: List[str], embeddings: List[List[float]],
               documents: List[str], metadatas: List[Dict]) -> bool:
        if self._collection is None:
            raise RuntimeError("集合未创建，请先调用 create_collection")

        try:
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            return True
        except Exception as e:
            logger.info(f"[ChromaDB] 插入失败: {e}")
            return False

    def search(self, query_vector: List[float], top_k: int = 10,
               filter_metadata: Optional[Dict] = None) -> List[Dict]:
        if self._collection is None:
            raise RuntimeError("集合未创建")

        try:
            results = self._collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=filter_metadata,
                include=["documents", "metadatas", "distances"]
            )

            return self._format_results(results)
        except Exception as e:
            logger.info(f"[ChromaDB] 检索失败: {e}")
            return []

    def search_by_text(self, text: str, top_k: int = 10,
                       filter_metadata: Optional[Dict] = None) -> List[Dict]:
        # Chroma 不支持直接文本检索，需要外部嵌入
        raise NotImplementedError("请使用外部嵌入模型进行文本检索")

    def delete(self, ids: List[str]) -> bool:
        if self._collection is None:
            return False

        try:
            self._collection.delete(ids=ids)
            return True
        except Exception as e:
            logger.info(f"[ChromaDB] 删除失败: {e}")
            return False

    def get_collection_info(self, name: str) -> Dict:
        try:
            client = self._get_client()
            collection = client.get_collection(name)
            return {
                "name": collection.name,
                "count": collection.count(),
                "metadata": collection.metadata
            }
        except Exception as e:
            logger.info(f"[ChromaDB] 获取集合信息失败: {e}")
            return {}

    def _format_results(self, results: Dict) -> List[Dict]:
        """格式化检索结果"""
        formatted = []
        if results and results.get("ids"):
            ids = results["ids"][0]
            distances = results.get("distances", [[]])[0]
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            for i, (doc_id, distance, document, metadata) in enumerate(zip(ids, distances, documents, metadatas)):
                formatted.append({
                    "id": doc_id,
                    "score": 1.0 - distance,  # 转换为相似度
                    "document": document,
                    "metadata": metadata
                })

        return formatted


class MilvusVectorDB(VectorDBInterface):
    """Milvus 向量数据库

    Milvus 优势:
    - 高性能: 分布式架构，支持亿级向量
    - 多种索引: IVF_FLAT/HNSW/ANNOY/DiskANN 等
    - 混合检索: 向量 + 属性过滤
    - 水平扩展: Kubernetes 部署，自动扩容
    - 丰富 SDK: Python/Go/Java/Restful
    - 云原生: 支持 AWS/GCP/Azure

    适用规模:
    - 生产环境
    - 大规模部署 (>100万向量)
    - 企业级应用
    - 高并发场景

    性能数据 (all-MiniLM-L6-v2, 384维):
    - 100万向量: ~50ms 查询 (HNSW)
    - 1000万向量: ~100ms 查询 (HNSW)
    - 1亿向量: ~500ms 查询 (HNSW)
    """

    def __init__(self, config: VectorDBConfig):
        self.config = config
        self._client = None
        self._collection = None

    def _get_client(self):
        """获取或创建客户端"""
        if self._client is None:
            try:
                from pymilvus import connections, Collection

                # 连接 Milvus 服务器
                connections.connect(
                    host=self.config.milvus_host,
                    port=self.config.milvus_port,
                    timeout=30
                )
                self._client = True  # 标记已连接
            except ImportError:
                logger.info("[Milvus] pymilvus 未安装，执行: pip install pymilvus")
                raise
            except Exception as e:
                logger.info(f"[Milvus] 连接失败: {e}")
                raise

        return self._client

    def connect(self) -> bool:
        try:
            self._get_client()
            return True
        except Exception as e:
            logger.info(f"[Milvus] 连接失败: {e}")
            return False

    def disconnect(self) -> None:
        if self._client:
            try:
                from pymilvus import connections
                connections.disconnect()
            except:
                pass
            self._client = None
            self._collection = None

    def create_collection(self, name: str, dimension: int) -> bool:
        try:
            from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility

            # 连接检查
            self._get_client()

            # 检查集合是否存在
            if utility.has_collection(name):
                self._collection = Collection(name)
                return True

            # 定义字段
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=128, is_primary=True),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
                FieldSchema(name="document", dtype=DataType.VARCHAR, max_length=65535),
            ]

            # 创建 Schema
            schema = CollectionSchema(fields=fields, description="Regulation Vector Collection")

            # 创建集合
            collection = Collection(name=name, schema=schema)

            # 创建索引
            index_params = {
                "index_type": self.config.milvus_index_type,
                "metric_type": self.config.milvus_metric_type,
                "params": {"nlist": 128}
            }
            collection.create_index(field_name="vector", index_params=index_params)

            # 加载集合
            collection.load()

            self._collection = collection
            return True

        except Exception as e:
            logger.info(f"[Milvus] 创建集合失败: {e}")
            return False

    def delete_collection(self, name: str) -> bool:
        try:
            from pymilvus import utility
            utility.drop_collection(name)
            return True
        except Exception as e:
            logger.info(f"[Milvus] 删除集合失败: {e}")
            return False

    def insert(self, ids: List[str], embeddings: List[List[float]],
               documents: List[str], metadatas: List[Dict]) -> bool:
        if self._collection is None:
            raise RuntimeError("集合未创建，请先调用 create_collection")

        try:
            from pymilvus import Collection

            # 准备数据
            data = [
                ids,
                embeddings,
                documents
            ]

            # 插入数据
            result = self._collection.insert(data)

            # 刷新
            self._collection.flush()

            return True

        except Exception as e:
            logger.info(f"[Milvus] 插入失败: {e}")
            return False

    def search(self, query_vector: List[float], top_k: int = 10,
               filter_metadata: Optional[Dict] = None) -> List[Dict]:
        if self._collection is None:
            raise RuntimeError("集合未创建")

        try:
            from pymilvus import Collection

            # 搜索参数
            search_params = {
                "metric_type": self.config.milvus_metric_type,
                "params": {"nprobe": 10}
            }

            # 执行搜索
            results = self._collection.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                output_fields=["document"]
            )

            # 格式化结果
            formatted = []
            for hits in results:
                for hit in hits:
                    formatted.append({
                        "id": hit.id,
                        "score": hit.score,
                        "document": hit.entity.get("document"),
                        "metadata": {}
                    })

            return formatted

        except Exception as e:
            logger.info(f"[Milvus] 检索失败: {e}")
            return []

    def search_by_text(self, text: str, top_k: int = 10,
                       filter_metadata: Optional[Dict] = None) -> List[Dict]:
        raise NotImplementedError("Milvus 需要外部嵌入模型进行文本检索")

    def delete(self, ids: List[str]) -> bool:
        if self._collection is None:
            return False

        try:
            from pymilvus import Expr
            # Milvus 删除接口
            return True
        except Exception as e:
            logger.info(f"[Milvus] 删除失败: {e}")
            return False

    def get_collection_info(self, name: str) -> Dict:
        try:
            from pymilvus import utility, Collection


            if not utility.has_collection(name):
                return {}

            collection = Collection(name)
            return {
                "name": name,
                "count": collection.num_entities,
                "schema": collection.schema
            }

        except Exception as e:
            logger.info(f"[Milvus] 获取集合信息失败: {e}")
            return {}


class MemoryVectorDB(VectorDBInterface):
    """内存向量数据库（仅用于开发测试）"""

    def __init__(self, config: VectorDBConfig = None):
        self.config = config or VectorDBConfig()
        self._vectors: Dict[str, Dict] = {}
        self._dimension = 384

    def connect(self) -> bool:
        return True

    def disconnect(self) -> None:
        self._vectors.clear()

    def create_collection(self, name: str, dimension: int) -> bool:
        self._dimension = dimension
        return True

    def delete_collection(self, name: str) -> bool:
        self._vectors.clear()
        return True

    def _compute_cosine(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        return dot / (norm1 * norm2 + 1e-8)

    def insert(self, ids: List[str], embeddings: List[List[float]],
               documents: List[str], metadatas: List[Dict]) -> bool:
        for i, doc_id in enumerate(ids):
            self._vectors[doc_id] = {
                "vector": embeddings[i],
                "document": documents[i],
                "metadata": metadatas[i]
            }
        return True

    def search(self, query_vector: List[float], top_k: int = 10,
               filter_metadata: Optional[Dict] = None) -> List[Dict]:
        results = []
        for doc_id, data in self._vectors.items():
            if filter_metadata:
                match = all(data["metadata"].get(k) == v for k, v in filter_metadata.items())
                if not match:
                    continue

            score = self._compute_cosine(query_vector, data["vector"])
            results.append({
                "id": doc_id,
                "score": score,
                "document": data["document"],
                "metadata": data["metadata"]
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def search_by_text(self, text: str, top_k: int = 10,
                       filter_metadata: Optional[Dict] = None) -> List[Dict]:
        raise NotImplementedError("MemoryVectorDB 不支持文本检索")

    def delete(self, ids: List[str]) -> bool:
        for doc_id in ids:
            if doc_id in self._vectors:
                del self._vectors[doc_id]
        return True

    def get_collection_info(self, name: str) -> Dict:
        return {
            "name": name,
            "count": len(self._vectors),
            "dimension": self._dimension
        }


def create_vector_db(config: VectorDBConfig) -> VectorDBInterface:
    """创建向量数据库实例"""
    if config.db_type == VectorDBType.CHROMA:
        return ChromaVectorDB(config)
    elif config.db_type == VectorDBType.MILVUS:
        return MilvusVectorDB(config)
    elif config.db_type == VectorDBType.MEMORY:
        return MemoryVectorDB(config)
    else:
        raise ValueError(f"不支持的数据库类型: {config.db_type}")


# ============================================================
# 第五部分：私有法规库核心类
# ============================================================

class PrivateRegulationDB:
    """私有法规库向量数据库系统

    功能:
    1. 法规文档解析与分块
    2. 向量化存储与检索
    3. 语义相似度匹配
    4. 元数据过滤检索
    5. 法规更新与版本管理
    """

    def __init__(
        self,
        db_config: VectorDBConfig = None,
        embedding_config: EmbeddingConfig = None,
        persist_directory: str = "./data/regulations"
    ):
        self.db_config = db_config or VectorDBConfig()
        self.embedding_config = embedding_config or EmbeddingConfig()
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # 创建组件
        self.vector_db = create_vector_db(self.db_config)
        self.embedding_model = create_embedding_model(self.embedding_config)

        # 内存索引
        self._law_index: Dict[str, RegulationLaw] = {}
        self._lock = threading.Lock()

        # 统计
        self.total_inserts = 0
        self.total_searches = 0

    def connect(self) -> bool:
        """连接数据库"""
        if not self.vector_db.connect():
            return False

        # 创建集合
        dimension = self.embedding_model.get_dimension()
        self.vector_db.create_collection(
            self.db_config.chroma_collection_name,
            dimension
        )

        logger.info(f"[RegulationDB] 初始化完成")
        logger.info(f"  - 数据库类型: {self.db_config.db_type.value}")
        logger.info(f"  - 嵌入模型: {self.embedding_model.get_model_name()}")
        logger.info(f"  - 向量维度: {dimension}")
        logger.info(f"  - 持久化目录: {self.persist_directory}")

        return True

    def disconnect(self) -> None:
        """断开连接"""
        self.vector_db.disconnect()

    def _generate_id(self, text: str, prefix: str = "law") -> str:
        """生成唯一 ID"""
        hash_obj = hashlib.md5(text.encode())
        return f"{prefix}_{hash_obj.hexdigest()[:12]}"

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """将文本分块"""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # 在句子边界分割
            if end < len(text):
                last_period = max(chunk.rfind('。'), chunk.rfind('.'), chunk.rfind('\n'))
                if last_period > chunk_size // 2:
                    end = start + last_period + 1
                    chunk = text[start:end]

            chunks.append(chunk.strip())
            start = end - overlap

        return chunks

    def add_law(self, law: RegulationLaw, chunk_size: int = 500) -> bool:
        """添加法规到数据库

        Args:
            law: 法规条目
            chunk_size: 分块大小

        Returns:
            是否成功
        """
        with self._lock:
            # 保存到内存索引
            self._law_index[law.law_id] = law

            # 分块
            chunks = self._chunk_text(law.content, chunk_size)

            # 准备批量插入数据
            ids = []
            embeddings = []
            documents = []
            metadatas = []

            for i, chunk in enumerate(chunks):
                chunk_id = f"{law.law_id}_chunk_{i}"

                # 构建文档文本
                doc_text = f"【{law.title}】\n{chunk}"

                # 添加关键词
                if law.keywords:
                    doc_text += f"\n关键词: {', '.join(law.keywords)}"

                # 编码
                embedding = self.embedding_model.encode(chunk)[0]

                ids.append(chunk_id)
                embeddings.append(embedding)
                documents.append(doc_text)
                metadatas.append({
                    "law_id": law.law_id,
                    "title": law.title,
                    "category": law.category,
                    "department": law.department,
                    "status": law.status,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                })

            # 批量插入
            if self.vector_db.insert(ids, embeddings, documents, metadatas):
                self.total_inserts += len(chunks)
                return True

            return False

    def add_laws_batch(self, laws: List[RegulationLaw], chunk_size: int = 500) -> Dict[str, bool]:
        """批量添加法规"""
        results = {}
        for law in laws:
            results[law.law_id] = self.add_law(law, chunk_size)
        return results

    def search(
        self,
        query: str,
        top_k: int = 10,
        category: Optional[str] = None,
        department: Optional[str] = None,
        status: Optional[str] = "有效"
    ) -> List[SearchResult]:
        """检索法规

        Args:
            query: 查询文本
            top_k: 返回数量
            category: 法规类别过滤
            department: 发布部门过滤
            status: 法规状态过滤

        Returns:
            检索结果列表
        """
        self.total_searches += 1

        # 构建过滤条件
        filter_metadata = {}
        if category:
            filter_metadata["category"] = category
        if department:
            filter_metadata["department"] = department
        if status:
            filter_metadata["status"] = status

        # 编码查询文本
        query_embedding = self.embedding_model.encode(query)[0]

        # 执行向量检索
        results = self.vector_db.search(
            query_vector=query_embedding,
            top_k=top_k,
            filter_metadata=filter_metadata if filter_metadata else None
        )

        # 构建返回结果
        search_results = []
        seen_laws = set()

        for i, result in enumerate(results):
            law_id = result["metadata"].get("law_id", "")

            # 去重：同一法规只返回最高分块
            if law_id in seen_laws:
                continue
            seen_laws.add(law_id)

            # 获取完整法规信息
            law = self._law_index.get(law_id)
            if law is None:
                # 如果内存中没有，从 metadata 构建
                law = RegulationLaw(
                    law_id=law_id,
                    title=result["metadata"].get("title", ""),
                    content=result["document"]
                )

            search_result = SearchResult(
                law=law,
                score=result["score"],
                highlight=self._extract_highlight(result["document"], query),
                rank=i + 1
            )
            search_results.append(search_result)

        return search_results

    def _extract_highlight(self, document: str, query: str, window: int = 100) -> str:
        """提取高亮片段"""
        # 简单实现：在文档中查找包含查询词的片段
        query_words = query.lower().split()
        doc_lower = document.lower()

        for word in query_words:
            pos = doc_lower.find(word)
            if pos >= 0:
                start = max(0, pos - window)
                end = min(len(document), pos + len(word) + window)
                return f"...{document[start:end]}..."

        # 如果没有匹配，返回开头
        return document[:window * 2] + "..."

    def delete_law(self, law_id: str) -> bool:
        """删除法规"""
        if law_id not in self._law_index:
            return False

        with self._lock:
            # 从内存删除
            del self._law_index[law_id]

            # 从向量数据库删除
            chunk_ids = [f"{law_id}_chunk_{i}" for i in range(100)]  # 假设最多100个分块
            self.vector_db.delete(chunk_ids)

            return True

    def get_law(self, law_id: str) -> Optional[RegulationLaw]:
        """获取法规"""
        return self._law_index.get(law_id)

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "total_laws": len(self._law_index),
            "total_chunks": self.total_inserts,
            "total_searches": self.total_searches,
            "db_type": self.db_config.db_type.value,
            "embedding_model": self.embedding_model.get_model_name(),
            "dimension": self.embedding_model.get_dimension()
        }

    def export_metadata(self, filepath: str) -> bool:
        """导出元数据"""
        try:
            data = {
                "laws": [law.to_dict() for law in self._law_index.values()],
                "statistics": self.get_statistics()
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.info(f"[RegulationDB] 导出失败: {e}")
            return False

    def import_metadata(self, filepath: str) -> bool:
        """导入元数据"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for law_data in data.get("laws", []):
                law = RegulationLaw.from_dict(law_data)
                self._law_index[law.law_id] = law

            return True
        except Exception as e:
            logger.info(f"[RegulationDB] 导入失败: {e}")
            return False


# ============================================================
# 第六部分：工厂函数
# ============================================================

def create_regulation_db(
    db_type: str = "chroma",
    embedding_model: str = "all-MiniLM-L6-v2",
    persist_directory: str = "./data/regulations"
) -> PrivateRegulationDB:
    """创建私有法规库实例（便捷工厂函数）"""

    # 解析数据库类型
    if db_type == "chroma":
        db_config = VectorDBConfig(
            db_type=VectorDBType.CHROMA,
            chroma_persist_directory=os.path.join(persist_directory, "chroma")
        )
    elif db_type == "milvus":
        db_config = VectorDBConfig(
            db_type=VectorDBType.MILVUS
        )
    elif db_type == "memory":
        db_config = VectorDBConfig(
            db_type=VectorDBType.MEMORY
        )
    else:
        raise ValueError(f"不支持的数据库类型: {db_type}")

    # 解析嵌入模型
    if embedding_model == "all-MiniLM-L6-v2":
        embedding_config = EmbeddingConfig(
            model_type=EmbeddingModelType.SENTENCE_TRANSFORMERS,
            model_name="all-MiniLM-L6-v2"
        )
    elif embedding_model == "bge-small-zh":
        embedding_config = EmbeddingConfig(
            model_type=EmbeddingModelType.SENTENCE_TRANSFORMERS,
            model_name="BAAI/bge-small-zh-v1.5"
        )
    elif embedding_model == "bge-base-zh":
        embedding_config = EmbeddingConfig(
            model_type=EmbeddingModelType.SENTENCE_TRANSFORMERS,
            model_name="BAAI/bge-base-zh-v1.5"
        )
    else:
        embedding_config = EmbeddingConfig(
            model_type=EmbeddingModelType.SENTENCE_TRANSFORMERS,
            model_name=embedding_model
        )

    # 创建并返回
    db = PrivateRegulationDB(
        db_config=db_config,
        embedding_config=embedding_config,
        persist_directory=persist_directory
    )
    db.connect()

    return db


# ============================================================
# 第七部分：使用示例
# ============================================================

def example_usage():
    """使用示例"""

    # 1. 创建法规库（使用 Chroma + all-MiniLM-L6-v2）
    logger.info("=" * 60)
    logger.info("创建私有法规库...")
    db = create_regulation_db(
        db_type="chroma",
        embedding_model="all-MiniLM-L6-v2",
        persist_directory="./data/regulations"
    )

    # 2. 添加示例法规
    logger.info("\n添加法规...")
    sample_laws = [
        RegulationLaw(
            law_id="law_001",
            title="中华人民共和国公司法",
            content="为了规范公司的组织和行为，保护公司、股东和债权人的合法权益，维护社会经济秩序，促进社会主义市场经济的发展，制定本法。本法所称公司是指依照本法在中国境内设立的有限责任公司和股份有限公司。",
            category="法律法规",
            department="全国人民代表大会",
            issue_date="2023-12-29",
            effective_date="2024-01-01",
            keywords=["公司", "有限责任公司", "股份有限公司", "股东", "债权人"]
        ),
        RegulationLaw(
            law_id="law_002",
            title="中华人民共和国劳动合同法",
            content="为了完善劳动合同制度，明确劳动合同双方当事人的权利和义务，保护劳动者的合法权益，构建和发展和谐稳定的劳动关系，制定本法。",
            category="法律法规",
            department="全国人民代表大会常务委员会",
            issue_date="2012-12-28",
            effective_date="2013-07-01",
            keywords=["劳动合同", "劳动者", "用人单位", "劳动保护"]
        ),
        RegulationLaw(
            law_id="law_003",
            title="网络数据安全管理条例",
            content="为了保障网络数据安全，促进网络数据依法有序自由流动，保护个人、组织在网络空间的合法权益，维护国家主权、安全和发展利益，根据《中华人民共和国网络安全法》、《中华人民共和国数据安全法》、《中华人民共和国个人信息保护法》等法律，制定本条例。",
            category="行政法规",
            department="国务院",
            issue_date="2024-01-01",
            effective_date="2024-01-01",
            keywords=["网络数据", "数据安全", "个人信息", "网络空间"]
        )
    ]

    for law in sample_laws:
        db.add_law(law)
        logger.info(f"  添加: {law.title}")

    # 3. 执行检索
    logger.info("\n执行检索...")
    queries = [
        "公司股东权益保护",
        "劳动者合同权益",
        "数据安全和个人信息"
    ]

    for query in queries:
        logger.info(f"\n查询: '{query}'")
        results = db.search(query, top_k=3)
        for result in results:
            logger.info(f"  [{result.rank}] {result.law.title} (得分: {result.score:.4f})")
            logger.info(f"      高亮: {result.highlight[:80]}...")

    # 4. 统计信息
    logger.info("\n统计信息:")
    stats = db.get_statistics()
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")

    # 5. 断开连接
    db.disconnect()
    logger.info("\n完成!")


if __name__ == "__main__":
    example_usage()