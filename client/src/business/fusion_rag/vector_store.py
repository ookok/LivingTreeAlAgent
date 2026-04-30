"""
向量数据库统一抽象层

提供：
1. 统一接口支持 Chroma 和 Qdrant
2. 一键切换数据库后端
3. 性能监控与评估
4. 数据迁移工具

策略：先用 Chroma 快速落地，后期可一键迁移到 Qdrant

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import os
import uuid
from typing import Dict, List, Any, Optional, Protocol, runtime_checkable
from loguru import logger


@runtime_checkable
class VectorStore(Protocol):
    """向量存储抽象接口"""
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """添加文档"""
        ...
    
    def query(
        self,
        query_texts: List[str],
        n_results: int = 10,
        where: Optional[Dict] = None,
        where_document: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """查询文档"""
        ...
    
    def get_documents(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """获取文档"""
        ...
    
    def update_documents(
        self,
        ids: List[str],
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict]] = None
    ):
        """更新文档"""
        ...
    
    def delete_documents(self, ids: List[str]):
        """删除文档"""
        ...
    
    def count(self) -> int:
        """获取文档数量"""
        ...
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        ...


class ChromaVectorStore:
    """Chroma 向量存储实现"""
    
    def __init__(self, persist_directory: str = "./data/chroma"):
        self._persist_directory = persist_directory
        self._client = None
        self._collection = None
        self._use_fallback = False
        self._fallback_documents = {}
        self._initialize()
    
    def _initialize(self):
        """初始化"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            os.makedirs(self._persist_directory, exist_ok=True)
            
            self._client = chromadb.Client(
                Settings(
                    persist_directory=self._persist_directory,
                    anonymized_telemetry=False
                )
            )
            
            self._collection = self._client.get_or_create_collection(
                name="fusion_rag_knowledge_base",
                metadata={"description": "FusionRAG 知识库"}
            )
            
            logger.info(f"Chroma 初始化完成，存储目录: {self._persist_directory}")
            
        except ImportError:
            self._use_fallback = True
            logger.warning("Chroma 未安装，使用内存模拟模式")
    
    def add_documents(self, documents, metadatas=None, ids=None):
        if self._use_fallback:
            return self._fallback_add(documents, metadatas, ids)
        
        if ids is None:
            ids = [f"doc_{uuid.uuid4().hex[:8]}" for _ in documents]
        
        self._collection.add(documents=documents, metadatas=metadatas, ids=ids)
        self._client.persist()
        return ids
    
    def query(self, query_texts, n_results=10, where=None, where_document=None):
        if self._use_fallback:
            return self._fallback_query(query_texts, n_results, where)
        
        return self._collection.query(
            query_texts=query_texts,
            n_results=n_results,
            where=where,
            where_document=where_document
        )
    
    def get_documents(self, ids=None, where=None):
        if self._use_fallback:
            return self._fallback_get(ids, where)
        return self._collection.get(ids=ids, where=where)
    
    def update_documents(self, ids, documents=None, metadatas=None):
        if self._use_fallback:
            return self._fallback_update(ids, documents, metadatas)
        
        self._collection.update(ids=ids, documents=documents, metadatas=metadatas)
        self._client.persist()
    
    def delete_documents(self, ids):
        if self._use_fallback:
            return self._fallback_delete(ids)
        
        self._collection.delete(ids=ids)
        self._client.persist()
    
    def count(self):
        if self._use_fallback:
            return len(self._fallback_documents)
        return self._collection.count()
    
    def get_stats(self):
        if self._use_fallback:
            return {
                "backend": "chroma_fallback",
                "count": len(self._fallback_documents),
                "persisted": False
            }
        return {
            "backend": "chroma",
            "count": self._collection.count(),
            "persisted": True,
            "directory": self._persist_directory
        }
    
    # 降级实现
    def _fallback_add(self, documents, metadatas, ids):
        if ids is None:
            ids = [f"doc_{uuid.uuid4().hex[:8]}" for _ in documents]
        for i, doc_id in enumerate(ids):
            self._fallback_documents[doc_id] = {
                "content": documents[i],
                "metadata": metadatas[i] if metadatas else {}
            }
        return ids
    
    def _fallback_query(self, query_texts, n_results, where):
        results = []
        for query in query_texts:
            query_lower = query.lower()
            matched = []
            for doc_id, data in self._fallback_documents.items():
                if query_lower in data["content"].lower():
                    if where:
                        match = True
                        for key, value in where.items():
                            if data["metadata"].get(key) != value:
                                match = False
                                break
                        if not match:
                            continue
                    matched.append({
                        "id": doc_id,
                        "content": data["content"],
                        "metadata": data["metadata"],
                        "distance": 0.5
                    })
            matched.sort(key=lambda x: x["distance"])
            results.append(matched[:n_results])
        
        return {
            "ids": [[r["id"] for r in res] for res in results],
            "documents": [[r["content"] for r in res] for res in results],
            "metadatas": [[r["metadata"] for r in res] for res in results],
            "distances": [[r["distance"] for r in res] for res in results]
        }
    
    def _fallback_get(self, ids, where):
        if ids:
            return [self._fallback_documents.get(doc_id) for doc_id in ids]
        return list(self._fallback_documents.values())
    
    def _fallback_update(self, ids, documents, metadatas):
        for i, doc_id in enumerate(ids):
            if doc_id in self._fallback_documents:
                if documents:
                    self._fallback_documents[doc_id]["content"] = documents[i]
                if metadatas:
                    self._fallback_documents[doc_id]["metadata"] = metadatas[i]
    
    def _fallback_delete(self, ids):
        for doc_id in ids:
            if doc_id in self._fallback_documents:
                del self._fallback_documents[doc_id]


class QdrantVectorStore:
    """Qdrant 向量存储实现"""
    
    def __init__(self, url: str = "http://localhost:6333", api_key: Optional[str] = None):
        self._url = url
        self._api_key = api_key
        self._client = None
        self._collection_name = "fusion_rag_knowledge_base"
        self._use_fallback = False
        self._fallback_documents = {}
        self._initialize()
    
    def _initialize(self):
        """初始化"""
        try:
            from qdrant_client import QdrantClient
            
            self._client = QdrantClient(
                url=self._url,
                api_key=self._api_key
            )
            
            # 检查集合是否存在，不存在则创建
            collections = self._client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self._collection_name not in collection_names:
                self._client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config={
                        "text": {"size": 384, "distance": "Cosine"}
                    }
                )
            
            logger.info(f"Qdrant 初始化完成，连接: {self._url}")
            
        except ImportError:
            self._use_fallback = True
            logger.warning("Qdrant 未安装，使用内存模拟模式")
        
        except Exception as e:
            self._use_fallback = True
            logger.warning(f"Qdrant 连接失败，使用内存模拟模式: {e}")
    
    def add_documents(self, documents, metadatas=None, ids=None):
        if self._use_fallback:
            return self._fallback_add(documents, metadatas, ids)
        
        if ids is None:
            ids = [f"doc_{uuid.uuid4().hex[:8]}" for _ in documents]
        
        from qdrant_client.models import PointStruct
        
        points = []
        for i, doc_id in enumerate(ids):
            points.append(PointStruct(
                id=doc_id,
                vector={"text": [0.0] * 384},  # 占位向量
                payload={
                    "content": documents[i],
                    "metadata": metadatas[i] if metadatas else {}
                }
            ))
        
        self._client.upsert(
            collection_name=self._collection_name,
            points=points
        )
        
        return ids
    
    def query(self, query_texts, n_results=10, where=None, where_document=None):
        if self._use_fallback:
            return self._fallback_query(query_texts, n_results, where)
        
        # 简化实现，实际应该使用向量查询
        results = []
        for query in query_texts:
            query_lower = query.lower()
            
            # 使用 Qdrant 的过滤查询
            filter_condition = None
            if where:
                filter_condition = {
                    "must": [
                        {"key": f"metadata.{k}", "match": {"value": v}}
                        for k, v in where.items()
                    ]
                }
            
            # 实际应该用向量搜索，这里简化为全量扫描
            all_points = self._client.scroll(
                collection_name=self._collection_name,
                limit=100,
                with_payload=True
            )
            
            matched = []
            for point in all_points[0]:
                content = point.payload.get("content", "")
                if query_lower in content.lower():
                    matched.append({
                        "id": point.id,
                        "content": content,
                        "metadata": point.payload.get("metadata", {}),
                        "distance": 0.5
                    })
            
            matched.sort(key=lambda x: x["distance"])
            results.append(matched[:n_results])
        
        return {
            "ids": [[r["id"] for r in res] for res in results],
            "documents": [[r["content"] for r in res] for res in results],
            "metadatas": [[r["metadata"] for r in res] for res in results],
            "distances": [[r["distance"] for r in res] for res in results]
        }
    
    def get_documents(self, ids=None, where=None):
        if self._use_fallback:
            return self._fallback_get(ids, where)
        
        if ids:
            results = self._client.retrieve(
                collection_name=self._collection_name,
                ids=ids
            )
            return [{
                "id": r.id,
                "content": r.payload.get("content"),
                "metadata": r.payload.get("metadata", {})
            } for r in results]
        
        all_points = self._client.scroll(
            collection_name=self._collection_name,
            limit=1000,
            with_payload=True
        )
        return [{
            "id": point.id,
            "content": point.payload.get("content"),
            "metadata": point.payload.get("metadata", {})
        } for point in all_points[0]]
    
    def update_documents(self, ids, documents=None, metadatas=None):
        if self._use_fallback:
            return self._fallback_update(ids, documents, metadatas)
        
        from qdrant_client.models import PointStruct
        
        points = []
        for i, doc_id in enumerate(ids):
            existing = self.get_documents([doc_id])[0] if ids else None
            
            point = PointStruct(
                id=doc_id,
                vector={"text": [0.0] * 384},
                payload={
                    "content": documents[i] if documents else existing.get("content", ""),
                    "metadata": metadatas[i] if metadatas else existing.get("metadata", {})
                }
            )
            points.append(point)
        
        self._client.upsert(
            collection_name=self._collection_name,
            points=points
        )
    
    def delete_documents(self, ids):
        if self._use_fallback:
            return self._fallback_delete(ids)
        
        self._client.delete(
            collection_name=self._collection_name,
            points_selector={"ids": ids}
        )
    
    def count(self):
        if self._use_fallback:
            return len(self._fallback_documents)
        
        try:
            info = self._client.get_collection(self._collection_name)
            return info.points_count
        except:
            return 0
    
    def get_stats(self):
        if self._use_fallback:
            return {
                "backend": "qdrant_fallback",
                "count": len(self._fallback_documents),
                "persisted": False
            }
        return {
            "backend": "qdrant",
            "count": self.count(),
            "persisted": True,
            "url": self._url
        }
    
    # 降级实现（同 Chroma）
    def _fallback_add(self, documents, metadatas, ids):
        if ids is None:
            ids = [f"doc_{uuid.uuid4().hex[:8]}" for _ in documents]
        for i, doc_id in enumerate(ids):
            self._fallback_documents[doc_id] = {
                "content": documents[i],
                "metadata": metadatas[i] if metadatas else {}
            }
        return ids
    
    def _fallback_query(self, query_texts, n_results, where):
        results = []
        for query in query_texts:
            query_lower = query.lower()
            matched = []
            for doc_id, data in self._fallback_documents.items():
                if query_lower in data["content"].lower():
                    if where:
                        match = True
                        for key, value in where.items():
                            if data["metadata"].get(key) != value:
                                match = False
                                break
                        if not match:
                            continue
                    matched.append({
                        "id": doc_id,
                        "content": data["content"],
                        "metadata": data["metadata"],
                        "distance": 0.5
                    })
            matched.sort(key=lambda x: x["distance"])
            results.append(matched[:n_results])
        
        return {
            "ids": [[r["id"] for r in res] for res in results],
            "documents": [[r["content"] for r in res] for res in results],
            "metadatas": [[r["metadata"] for r in res] for res in results],
            "distances": [[r["distance"] for r in res] for res in results]
        }
    
    def _fallback_get(self, ids, where):
        if ids:
            return [self._fallback_documents.get(doc_id) for doc_id in ids]
        return list(self._fallback_documents.values())
    
    def _fallback_update(self, ids, documents, metadatas):
        for i, doc_id in enumerate(ids):
            if doc_id in self._fallback_documents:
                if documents:
                    self._fallback_documents[doc_id]["content"] = documents[i]
                if metadatas:
                    self._fallback_documents[doc_id]["metadata"] = metadatas[i]
    
    def _fallback_delete(self, ids):
        for doc_id in ids:
            if doc_id in self._fallback_documents:
                del self._fallback_documents[doc_id]


class VectorStoreManager:
    """向量存储管理器 - 支持一键切换后端"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorStoreManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self, backend: str = "chroma", config: Optional[Dict] = None):
        """
        初始化向量存储管理器
        
        Args:
            backend: 后端类型，支持 "chroma" 或 "qdrant"
            config: 配置字典
        """
        if self._initialized:
            return
        
        config = config or {}
        self._backend = backend
        self._config = config
        
        if backend == "qdrant":
            self._store = QdrantVectorStore(
                url=config.get("url", "http://localhost:6333"),
                api_key=config.get("api_key")
            )
        else:
            self._store = ChromaVectorStore(
                persist_directory=config.get("persist_directory", "./data/chroma")
            )
        
        # 初始化性能监控
        self._performance_monitor = PerformanceMonitor()
        
        self._initialized = True
        logger.info(f"VectorStoreManager 初始化完成，后端: {backend}")
    
    def switch_backend(self, backend: str, config: Optional[Dict] = None):
        """
        切换后端
        
        Args:
            backend: 新后端类型
            config: 新配置
        
        Returns:
            是否切换成功
        """
        if backend == self._backend:
            logger.info(f"已经使用 {backend} 后端")
            return True
        
        try:
            # 先导出数据
            data = self._export_data()
            
            # 初始化新后端
            config = config or {}
            if backend == "qdrant":
                new_store = QdrantVectorStore(
                    url=config.get("url", "http://localhost:6333"),
                    api_key=config.get("api_key")
                )
            else:
                new_store = ChromaVectorStore(
                    persist_directory=config.get("persist_directory", "./data/chroma")
                )
            
            # 导入数据
            self._import_data(new_store, data)
            
            # 切换
            self._store = new_store
            self._backend = backend
            
            logger.info(f"成功切换到 {backend} 后端")
            return True
            
        except Exception as e:
            logger.error(f"切换后端失败: {e}")
            return False
    
    def _export_data(self) -> Dict[str, Any]:
        """导出当前数据"""
        all_docs = self._store.get_documents()
        
        documents = []
        metadatas = []
        ids = []
        
        for doc in all_docs:
            if doc:
                ids.append(doc["id"])
                documents.append(doc["content"])
                metadatas.append(doc.get("metadata", {}))
        
        return {
            "documents": documents,
            "metadatas": metadatas,
            "ids": ids
        }
    
    def _import_data(self, store: VectorStore, data: Dict[str, Any]):
        """导入数据到新存储"""
        if data["documents"]:
            store.add_documents(
                documents=data["documents"],
                metadatas=data["metadatas"],
                ids=data["ids"]
            )
    
    def add_documents(self, documents, metadatas=None, ids=None):
        """添加文档（带性能监控）"""
        with self._performance_monitor.track("add_documents"):
            return self._store.add_documents(documents, metadatas, ids)
    
    def query(self, query_texts, n_results=10, where=None, where_document=None):
        """查询文档（带性能监控）"""
        with self._performance_monitor.track("query"):
            return self._store.query(query_texts, n_results, where, where_document)
    
    def get_documents(self, ids=None, where=None):
        """获取文档"""
        return self._store.get_documents(ids, where)
    
    def update_documents(self, ids, documents=None, metadatas=None):
        """更新文档"""
        return self._store.update_documents(ids, documents, metadatas)
    
    def delete_documents(self, ids):
        """删除文档"""
        return self._store.delete_documents(ids)
    
    def count(self):
        """获取文档数量"""
        return self._store.count()
    
    def get_stats(self):
        """获取统计信息"""
        stats = self._store.get_stats()
        stats["backend"] = self._backend
        stats["performance"] = self._performance_monitor.get_metrics()
        return stats
    
    def get_performance_report(self):
        """获取性能报告"""
        return self._performance_monitor.generate_report()
    
    def evaluate_performance(self) -> Dict[str, Any]:
        """评估性能，决定是否需要迁移"""
        metrics = self._performance_monitor.get_metrics()
        count = self._store.count()
        
        evaluation = {
            "current_backend": self._backend,
            "document_count": count,
            "recommendations": []
        }
        
        # 基于指标给出迁移建议
        if count > 10000:
            evaluation["recommendations"].append({
                "level": "high",
                "message": "文档数量超过 10,000，建议考虑迁移到 Qdrant 以获得更好的性能"
            })
        
        if metrics.get("query_latency_avg", 0) > 2.0:
            evaluation["recommendations"].append({
                "level": "high",
                "message": "平均查询延迟超过 2 秒，建议优化或迁移"
            })
        
        if metrics.get("query_latency_p95", 0) > 5.0:
            evaluation["recommendations"].append({
                "level": "medium",
                "message": "P95 查询延迟超过 5 秒，建议关注"
            })
        
        if metrics.get("throughput", 0) < 10:
            evaluation["recommendations"].append({
                "level": "medium",
                "message": "吞吐量低于 10 QPS，当前配置可能不足"
            })
        
        if not evaluation["recommendations"]:
            evaluation["recommendations"].append({
                "level": "low",
                "message": "当前性能良好，无需迁移"
            })
        
        return evaluation
    
    @classmethod
    def get_instance(cls) -> "VectorStoreManager":
        """获取实例"""
        instance = cls()
        if not instance._initialized:
            instance.initialize()
        return instance


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self._metrics = {
            "add_documents": {
                "count": 0,
                "total_time": 0.0,
                "min_time": float("inf"),
                "max_time": 0.0
            },
            "query": {
                "count": 0,
                "total_time": 0.0,
                "min_time": float("inf"),
                "max_time": 0.0,
                "latencies": []
            }
        }
    
    def track(self, operation: str):
        """上下文管理器，跟踪操作时间"""
        import time
        
        monitor = self  # 保存外部引用
        
        class Timer:
            def __enter__(self):
                self.start = time.time()
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                elapsed = time.time() - self.start
                
                if operation in monitor._metrics:
                    monitor._metrics[operation]["count"] += 1
                    monitor._metrics[operation]["total_time"] += elapsed
                    monitor._metrics[operation]["min_time"] = min(
                        monitor._metrics[operation]["min_time"], elapsed
                    )
                    monitor._metrics[operation]["max_time"] = max(
                        monitor._metrics[operation]["max_time"], elapsed
                    )
                    
                    if operation == "query":
                        monitor._metrics[operation]["latencies"].append(elapsed)
                        # 保持最多 1000 个延迟记录
                        if len(monitor._metrics[operation]["latencies"]) > 1000:
                            monitor._metrics[operation]["latencies"].pop(0)
        
        return Timer()
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        result = {}
        
        for op, data in self._metrics.items():
            if data["count"] > 0:
                avg_time = data["total_time"] / data["count"]
                result[f"{op}_count"] = data["count"]
                result[f"{op}_latency_avg"] = round(avg_time, 4)
                result[f"{op}_latency_min"] = round(data["min_time"], 4)
                result[f"{op}_latency_max"] = round(data["max_time"], 4)
                
                if op == "query" and data["latencies"]:
                    sorted_latencies = sorted(data["latencies"])
                    p95_idx = int(len(sorted_latencies) * 0.95)
                    result["query_latency_p95"] = round(
                        sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else avg_time,
                        4
                    )
                    result["throughput"] = round(data["count"] / max(data["total_time"], 1), 2)
        
        return result
    
    def generate_report(self) -> str:
        """生成性能报告"""
        metrics = self.get_metrics()
        report = ["=" * 60]
        report.append("向量存储性能报告")
        report.append("=" * 60)
        
        if "query_count" in metrics:
            report.append(f"查询次数: {metrics['query_count']}")
            report.append(f"平均延迟: {metrics['query_latency_avg']:.4f}s")
            report.append(f"最小延迟: {metrics['query_latency_min']:.4f}s")
            report.append(f"最大延迟: {metrics['query_latency_max']:.4f}s")
            if "query_latency_p95" in metrics:
                report.append(f"P95 延迟: {metrics['query_latency_p95']:.4f}s")
            if "throughput" in metrics:
                report.append(f"吞吐量: {metrics['throughput']:.2f} QPS")
        
        if "add_documents_count" in metrics:
            report.append(f"\n添加文档次数: {metrics['add_documents_count']}")
            report.append(f"平均耗时: {metrics['add_documents_latency_avg']:.4f}s")
        
        report.append("=" * 60)
        return "\n".join(report)


# 快捷函数
def get_vector_store() -> VectorStoreManager:
    """获取向量存储管理器实例"""
    return VectorStoreManager.get_instance()


def switch_to_chroma(config: Optional[Dict] = None):
    """切换到 Chroma 后端"""
    manager = VectorStoreManager.get_instance()
    return manager.switch_backend("chroma", config)


def switch_to_qdrant(config: Optional[Dict] = None):
    """切换到 Qdrant 后端"""
    manager = VectorStoreManager.get_instance()
    return manager.switch_backend("qdrant", config)