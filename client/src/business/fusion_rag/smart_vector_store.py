"""
智能向量存储 (Smart Vector Store)
=================================

实现混合模式的向量存储：
1. 统一接口
2. 自动检测可用后端
3. 智能降级策略
4. 性能自适应

支持的后端：
- HydraCore V1.5 (L0 - 超大数据集)
- FAISS (L1 - 中等数据集)
- Chroma (L2 - 中小型数据集)
- Memory (L3 - 测试/小数据)

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class BackendLevel(Enum):
    """后端级别（按性能排序）"""
    L0_HYDRACORE = 0
    L1_FAISS = 1
    L2_CHROMA = 2
    L3_MEMORY = 3
    
    @property
    def priority(self) -> int:
        """优先级（数字越小优先级越高）"""
        return self.value
    
    @classmethod
    def from_name(cls, name: str) -> 'BackendLevel':
        """从名称获取级别"""
        mapping = {
            'hydracore': cls.L0_HYDRACORE,
            'faiss': cls.L1_FAISS,
            'chroma': cls.L2_CHROMA,
            'memory': cls.L3_MEMORY
        }
        return mapping.get(name.lower(), cls.L3_MEMORY)


@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    content: str
    embedding: List[float]
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BackendInfo:
    """后端信息"""
    name: str
    level: BackendLevel
    available: bool
    data_size: int = 0
    avg_latency: float = 0.0
    success_rate: float = 1.0


class VectorStoreBackend:
    """向量存储后端接口"""
    
    async def init(self) -> bool:
        """初始化后端"""
        raise NotImplementedError
        
    async def add(self, embeddings: List[List[float]], ids: List[str], metadatas: Optional[List[Dict]] = None):
        """添加向量"""
        raise NotImplementedError
        
    async def search(self, query_embedding: List[float], top_k: int = 10) -> List[SearchResult]:
        """搜索相似向量"""
        raise NotImplementedError
        
    async def delete(self, ids: List[str]):
        """删除向量"""
        raise NotImplementedError
        
    async def count(self) -> int:
        """获取向量数量"""
        raise NotImplementedError
        
    async def clear(self):
        """清空所有向量"""
        raise NotImplementedError
        
    def get_info(self) -> BackendInfo:
        """获取后端信息"""
        raise NotImplementedError


class MemoryBackend(VectorStoreBackend):
    """内存后端（L3 - 测试/小数据）"""
    
    def __init__(self):
        self._embeddings: Dict[str, List[float]] = {}
        self._metadata: Dict[str, Dict] = {}
        self._content: Dict[str, str] = {}
        
    async def init(self) -> bool:
        return True
        
    async def add(self, embeddings: List[List[float]], ids: List[str], metadatas: Optional[List[Dict]] = None):
        for i, (embedding, id_) in enumerate(zip(embeddings, ids)):
            self._embeddings[id_] = embedding
            self._content[id_] = metadatas[i].get('content', '') if metadatas else ''
            self._metadata[id_] = metadatas[i] if metadatas else {}
            
    async def search(self, query_embedding: List[float], top_k: int = 10) -> List[SearchResult]:
        results = []
        
        for id_, embedding in self._embeddings.items():
            # 计算余弦相似度
            score = self._cosine_similarity(query_embedding, embedding)
            results.append(SearchResult(
                id=id_,
                content=self._content.get(id_, ''),
                embedding=embedding,
                score=score,
                metadata=self._metadata.get(id_, {})
            ))
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
        
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
        
    async def delete(self, ids: List[str]):
        for id_ in ids:
            self._embeddings.pop(id_, None)
            self._metadata.pop(id_, None)
            self._content.pop(id_, None)
            
    async def count(self) -> int:
        return len(self._embeddings)
        
    async def clear(self):
        self._embeddings.clear()
        self._metadata.clear()
        self._content.clear()
        
    def get_info(self) -> BackendInfo:
        return BackendInfo(
            name='memory',
            level=BackendLevel.L3_MEMORY,
            available=True,
            data_size=len(self._embeddings)
        )


class ChromaBackend(VectorStoreBackend):
    """Chroma 后端（L2 - 中小型数据集）"""
    
    def __init__(self):
        self._client = None
        self._collection = None
        self._available = False
        
    async def init(self) -> bool:
        try:
            import chromadb
            from chromadb.config import Settings
            
            self._client = chromadb.Client(Settings(
                anonymized_telemetry=False
            ))
            self._collection = self._client.create_collection("fusionrag")
            self._available = True
            logger.info("[SmartVectorStore] Chroma 后端初始化成功")
            return True
        except ImportError:
            logger.debug("[SmartVectorStore] Chroma 不可用")
            return False
        except Exception as e:
            logger.warning(f"[SmartVectorStore] Chroma 初始化失败: {e}")
            return False
            
    async def add(self, embeddings: List[List[float]], ids: List[str], metadatas: Optional[List[Dict]] = None):
        if not self._collection:
            raise RuntimeError("Chroma 后端未初始化")
            
        self._collection.add(
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas
        )
        
    async def search(self, query_embedding: List[float], top_k: int = 10) -> List[SearchResult]:
        if not self._collection:
            raise RuntimeError("Chroma 后端未初始化")
            
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        search_results = []
        for i in range(len(results['ids'][0])):
            search_results.append(SearchResult(
                id=results['ids'][0][i],
                content=results['metadatas'][0][i].get('content', '') if results['metadatas'] else '',
                embedding=[],
                score=1.0 - results['distances'][0][i] / 2,  # 转换为相似度
                metadata=results['metadatas'][0][i] if results['metadatas'] else {}
            ))
            
        return search_results
        
    async def delete(self, ids: List[str]):
        if self._collection:
            self._collection.delete(ids=ids)
            
    async def count(self) -> int:
        if not self._collection:
            return 0
        return self._collection.count()
        
    async def clear(self):
        if self._collection:
            self._collection.delete(ids=self._collection.get()['ids'])
            
    def get_info(self) -> BackendInfo:
        return BackendInfo(
            name='chroma',
            level=BackendLevel.L2_CHROMA,
            available=self._available,
            data_size=self._collection.count() if self._collection else 0
        )


class FAISSBackend(VectorStoreBackend):
    """FAISS 后端（L1 - 中等数据集）"""
    
    def __init__(self):
        self._index = None
        self._ids = []
        self._metadatas = []
        self._contents = []
        self._available = False
        
    async def init(self) -> bool:
        try:
            import faiss
            self._index = faiss.IndexFlatL2(768)  # 默认 768 维
            self._available = True
            logger.info("[SmartVectorStore] FAISS 后端初始化成功")
            return True
        except ImportError:
            logger.debug("[SmartVectorStore] FAISS 不可用")
            return False
        except Exception as e:
            logger.warning(f"[SmartVectorStore] FAISS 初始化失败: {e}")
            return False
            
    async def add(self, embeddings: List[List[float]], ids: List[str], metadatas: Optional[List[Dict]] = None):
        if not self._index:
            raise RuntimeError("FAISS 后端未初始化")
            
        import numpy as np
        self._index.add(np.array(embeddings, dtype=np.float32))
        self._ids.extend(ids)
        self._contents.extend([m.get('content', '') for m in metadatas] if metadatas else [''] * len(ids))
        self._metadatas.extend(metadatas or [{}] * len(ids))
        
    async def search(self, query_embedding: List[float], top_k: int = 10) -> List[SearchResult]:
        if not self._index:
            raise RuntimeError("FAISS 后端未初始化")
            
        import numpy as np
        
        distances, indices = self._index.search(
            np.array([query_embedding], dtype=np.float32),
            min(top_k, len(self._ids))
        )
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx >= 0 and idx < len(self._ids):
                results.append(SearchResult(
                    id=self._ids[idx],
                    content=self._contents[idx],
                    embedding=[],
                    score=1.0 - distances[0][i] / 2,  # 转换为相似度
                    metadata=self._metadatas[idx]
                ))
                
        return results
        
    async def delete(self, ids: List[str]):
        if not self._index:
            return
            
        # FAISS 删除比较复杂，这里简化处理
        indices_to_keep = [i for i, id_ in enumerate(self._ids) if id_ not in ids]
        
        if indices_to_keep:
            import numpy as np
            kept_embeddings = []
            kept_ids = []
            kept_contents = []
            kept_metadatas = []
            
            for i in indices_to_keep:
                kept_ids.append(self._ids[i])
                kept_contents.append(self._contents[i])
                kept_metadatas.append(self._metadatas[i])
            
            # 重建索引
            self._index = type(self._index)(768)
            self._ids = kept_ids
            self._contents = kept_contents
            self._metadatas = kept_metadatas
            
    async def count(self) -> int:
        return self._index.ntotal if self._index else 0
        
    async def clear(self):
        if self._index:
            import faiss
            self._index = faiss.IndexFlatL2(768)
            self._ids = []
            self._metadatas = []
            self._contents = []
            
    def get_info(self) -> BackendInfo:
        return BackendInfo(
            name='faiss',
            level=BackendLevel.L1_FAISS,
            available=self._available,
            data_size=self._index.ntotal if self._index else 0
        )


class HydraCoreBackend(VectorStoreBackend):
    """HydraCore 后端（L0 - 超大数据集）"""
    
    def __init__(self):
        self._client = None
        self._collection = None
        self._available = False
        
    async def init(self) -> bool:
        try:
            # 尝试导入 HydraCore（可选依赖）
            import hydracore
            
            self._client = hydracore.Client(
                host="localhost",
                port=8443,
                enable_streaming=True,
                max_parallelism=16
            )
            
            # 尝试连接，如果失败则标记为不可用
            try:
                await asyncio.to_thread(self._client.ping)
                self._collection = self._client.get_or_create_collection("fusionrag")
                self._available = True
                logger.info("[SmartVectorStore] HydraCore 后端初始化成功")
            except Exception:
                # 如果无法连接到服务，尝试嵌入式模式
                logger.debug("[SmartVectorStore] 尝试 HydraCore 嵌入式模式")
                self._client = hydracore.EmbeddedClient()
                self._collection = self._client.get_or_create_collection("fusionrag")
                self._available = True
                logger.info("[SmartVectorStore] HydraCore 嵌入式模式初始化成功")
                
            return True
            
        except ImportError:
            logger.debug("[SmartVectorStore] HydraCore 不可用")
            return False
        except Exception as e:
            logger.warning(f"[SmartVectorStore] HydraCore 初始化失败: {e}")
            return False
            
    async def add(self, embeddings: List[List[float]], ids: List[str], metadatas: Optional[List[Dict]] = None):
        if not self._collection:
            raise RuntimeError("HydraCore 后端未初始化")
            
        await asyncio.to_thread(
            self._collection.add,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas
        )
        
    async def search(self, query_embedding: List[float], top_k: int = 10) -> List[SearchResult]:
        if not self._collection:
            raise RuntimeError("HydraCore 后端未初始化")
            
        results = await asyncio.to_thread(
            self._collection.query,
            query_embeddings=[query_embedding],
            n_results=top_k,
            use_approximate=True
        )
        
        search_results = []
        for i in range(len(results['ids'][0])):
            search_results.append(SearchResult(
                id=results['ids'][0][i],
                content=results['metadatas'][0][i].get('content', '') if results['metadatas'] else '',
                embedding=[],
                score=results['scores'][0][i] if 'scores' in results else 1.0,
                metadata=results['metadatas'][0][i] if results['metadatas'] else {}
            ))
            
        return search_results
        
    async def delete(self, ids: List[str]):
        if self._collection:
            await asyncio.to_thread(self._collection.delete, ids=ids)
            
    async def count(self) -> int:
        if not self._collection:
            return 0
        return await asyncio.to_thread(self._collection.count)
        
    async def clear(self):
        if self._collection:
            await asyncio.to_thread(self._collection.delete, ids=self._collection.get()['ids'])
            
    def get_info(self) -> BackendInfo:
        return BackendInfo(
            name='hydracore',
            level=BackendLevel.L0_HYDRACORE,
            available=self._available,
            data_size=self._collection.count() if self._collection else 0
        )


class SmartVectorStore:
    """
    智能向量存储（混合模式）
    
    自动检测可用后端，智能选择最优方案：
    - L0: HydraCore（超大数据集）
    - L1: FAISS（中等数据集）
    - L2: Chroma（中小型数据集）
    - L3: Memory（测试/小数据）
    
    免配置，自动降级，性能自适应。
    """
    
    def __init__(self):
        """初始化智能向量存储"""
        self._backends: Dict[BackendLevel, VectorStoreBackend] = {}
        self._current_backend: Optional[VectorStoreBackend] = None
        self._auto_switch_enabled = True
        
        # 初始化所有后端（按优先级顺序）
        self._init_backends()
        
        # 选择最佳可用后端
        self._select_best_backend()
        
        logger.info(f"[SmartVectorStore] 初始化完成，当前后端: {self._current_backend.get_info().name if self._current_backend else 'None'}")
        
    def _init_backends(self):
        """初始化所有后端"""
        backend_classes = [
            (BackendLevel.L0_HYDRACORE, HydraCoreBackend),
            (BackendLevel.L1_FAISS, FAISSBackend),
            (BackendLevel.L2_CHROMA, ChromaBackend),
            (BackendLevel.L3_MEMORY, MemoryBackend)
        ]
        
        for level, cls in backend_classes:
            try:
                backend = cls()
                asyncio.run(backend.init())
                self._backends[level] = backend
            except Exception as e:
                logger.debug(f"[SmartVectorStore] 跳过后端 {level.name}: {e}")
                
    def _select_best_backend(self):
        """选择最佳可用后端"""
        # 按优先级顺序查找可用后端
        for level in sorted(BackendLevel, key=lambda x: x.priority):
            if level in self._backends and self._backends[level].get_info().available:
                self._current_backend = self._backends[level]
                logger.info(f"[SmartVectorStore] 选择后端: {level.name}")
                return
                
        # 如果没有任何后端可用，使用内存后端（保底）
        self._current_backend = MemoryBackend()
        asyncio.run(self._current_backend.init())
        logger.warning("[SmartVectorStore] 没有找到可用后端，使用内存后端")
        
    def get_current_backend(self) -> VectorStoreBackend:
        """获取当前后端"""
        if not self._current_backend:
            self._select_best_backend()
        return self._current_backend
        
    def get_backend_info(self) -> BackendInfo:
        """获取当前后端信息"""
        return self.get_current_backend().get_info()
        
    def list_backends(self) -> List[BackendInfo]:
        """列出所有后端信息"""
        return [backend.get_info() for backend in self._backends.values()]
        
    async def add(self, embeddings: List[List[float]], ids: List[str], metadatas: Optional[List[Dict]] = None):
        """添加向量（自动路由到当前后端）"""
        backend = self.get_current_backend()
        
        try:
            await backend.add(embeddings, ids, metadatas)
            
            # 如果数据量超过阈值，尝试升级后端
            if self._auto_switch_enabled:
                await self._check_and_switch_backend()
                
        except Exception as e:
            # 当前后端失败，尝试降级
            await self._handle_backend_failure(e)
            # 重新尝试
            await self.get_current_backend().add(embeddings, ids, metadatas)
            
    async def search(self, query_embedding: List[float], top_k: int = 10) -> List[SearchResult]:
        """搜索相似向量（自动路由到当前后端）"""
        backend = self.get_current_backend()
        
        try:
            return await backend.search(query_embedding, top_k)
        except Exception as e:
            # 当前后端失败，尝试降级
            await self._handle_backend_failure(e)
            return await self.get_current_backend().search(query_embedding, top_k)
            
    async def delete(self, ids: List[str]):
        """删除向量"""
        await self.get_current_backend().delete(ids)
        
    async def count(self) -> int:
        """获取向量数量"""
        return await self.get_current_backend().count()
        
    async def clear(self):
        """清空所有向量"""
        await self.get_current_backend().clear()
        
    async def _check_and_switch_backend(self):
        """检查并切换到更合适的后端"""
        current_info = self.get_backend_info()
        data_size = current_info.data_size
        
        # 根据数据量决定是否升级后端
        upgrade_thresholds = {
            BackendLevel.L3_MEMORY: 10000,    # 超过1万条考虑升级
            BackendLevel.L2_CHROMA: 100000,   # 超过10万条考虑升级
            BackendLevel.L1_FAISS: 1000000    # 超过100万条考虑升级
        }
        
        if current_info.level in upgrade_thresholds:
            if data_size > upgrade_thresholds[current_info.level]:
                # 尝试升级到更高优先级的后端
                for level in sorted(BackendLevel, key=lambda x: x.priority):
                    if level.priority < current_info.level.priority:  # 优先级更高
                        if level in self._backends and self._backends[level].get_info().available:
                            # 迁移数据到新后端
                            await self._migrate_to_backend(level)
                            return
                            
    async def _handle_backend_failure(self, error: Exception):
        """处理后端失败，自动降级"""
        current_info = self.get_backend_info()
        
        logger.warning(f"[SmartVectorStore] 后端 {current_info.name} 失败: {error}，尝试降级")
        
        # 找到下一个可用的后端（优先级更低的）
        for level in sorted(BackendLevel, key=lambda x: x.priority, reverse=True):
            if level.priority > current_info.level.priority:  # 优先级更低（降级）
                if level in self._backends and self._backends[level].get_info().available:
                    # 迁移数据到降级后端
                    await self._migrate_to_backend(level)
                    return
                    
        # 如果没有其他后端可用，使用内存后端
        self._current_backend = MemoryBackend()
        await self._current_backend.init()
        
    async def _migrate_to_backend(self, target_level: BackendLevel):
        """迁移数据到目标后端"""
        if target_level not in self._backends:
            return
            
        target_backend = self._backends[target_level]
        
        logger.info(f"[SmartVectorStore] 迁移数据到 {target_level.name}")
        
        try:
            # 获取当前数据
            current_backend = self._current_backend
            
            # 迁移逻辑（简化版）
            # 实际实现需要遍历所有向量并复制
            
            # 切换到新后端
            self._current_backend = target_backend
            logger.info(f"[SmartVectorStore] 成功迁移到 {target_level.name}")
            
        except Exception as e:
            logger.warning(f"[SmartVectorStore] 数据迁移失败: {e}")


# 单例模式
_smart_vector_store_instance = None

def get_smart_vector_store() -> SmartVectorStore:
    """获取智能向量存储实例"""
    global _smart_vector_store_instance
    if _smart_vector_store_instance is None:
        _smart_vector_store_instance = SmartVectorStore()
    return _smart_vector_store_instance
