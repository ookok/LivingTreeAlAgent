"""
新皮层模块 - 语义记忆与推理
借鉴大脑新皮层的工作原理

功能：
1. 长期语义记忆存储
2. 知识图谱构建
3. 语义相似度检索
4. 多步推理
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class SemanticNode:
    """语义节点 - 知识图谱中的基本单元"""
    node_id: str
    content: str
    node_type: str
    embedding: Optional[List[float]] = None
    connections: Dict[str, float] = None
    metadata: Dict[str, Any] = None
    activation: float = 0.0  # 激活值
    
    def __post_init__(self):
        if self.connections is None:
            self.connections = {}
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        return {
            'node_id': self.node_id,
            'content': self.content,
            'node_type': self.node_type,
            'embedding': self.embedding,
            'connections': self.connections,
            'metadata': self.metadata,
            'activation': self.activation
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SemanticNode':
        return cls(**data)


class Neocortex:
    """
    新皮层 - 长期语义记忆存储与推理中心
    
    主要功能：
    1. 存储语义知识节点
    2. 构建知识图谱连接
    3. 语义相似度检索
    4. 知识推理与路径查找
    """
    
    def __init__(self, storage_path: str = "data/memory/neocortex"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._nodes: Dict[str, SemanticNode] = {}
        self._load_nodes()
        
        # 节点类型索引
        self._type_index: Dict[str, List[str]] = {}
        self._build_type_index()
        
        # 预计算的嵌入矩阵（用于快速相似度计算）
        self._embedding_matrix = None
        self._node_id_list = []
    
    def store_semantic(
        self,
        content: str,
        node_type: str = "concept",
        metadata: Optional[Dict] = None,
        connections: Optional[Dict[str, float]] = None
    ) -> str:
        """存储语义知识"""
        import uuid
        node_id = str(uuid.uuid4())
        
        node = SemanticNode(
            node_id=node_id,
            content=content,
            node_type=node_type,
            embedding=self._embed(content),
            connections=connections or {},
            metadata=metadata or {}
        )
        
        self._nodes[node_id] = node
        self._save_node(node)
        self._update_type_index(node)
        self._invalidate_embedding_cache()
        
        logger.debug(f"Stored semantic node: {node_id} [{node_type}]")
        return node_id
    
    def batch_store(self, items: List[Dict]) -> List[str]:
        """批量存储语义知识"""
        ids = []
        for item in items:
            node_id = self.store_semantic(
                content=item['content'],
                node_type=item.get('type', 'concept'),
                metadata=item.get('metadata'),
                connections=item.get('connections')
            )
            ids.append(node_id)
        return ids
    
    def retrieve_semantic(
        self,
        query: str,
        node_type: str = None,
        limit: int = 10,
        threshold: float = 0.3
    ) -> List[Dict]:
        """语义检索 - 基于向量相似度"""
        if not self._nodes:
            return []
        
        query_embedding = self._embed(query)
        
        # 使用缓存的嵌入矩阵进行批量计算
        if self._embedding_matrix is None:
            self._build_embedding_cache()
        
        # 计算相似度
        results = []
        for i, node_id in enumerate(self._node_id_list):
            node = self._nodes[node_id]
            if node.embedding is not None:
                similarity = float(cosine_similarity([query_embedding], [node.embedding])[0][0])
                
                # 类型过滤
                if node_type and node.node_type != node_type:
                    continue
                
                if similarity >= threshold:
                    results.append({
                        'node_id': node_id,
                        'content': node.content,
                        'node_type': node.node_type,
                        'similarity': round(similarity, 4),
                        'metadata': node.metadata,
                        'connections': len(node.connections)
                    })
        
        # 排序
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:limit]
    
    def make_inference(
        self,
        start_node_id: str,
        max_hops: int = 3,
        target_node_type: str = None
    ) -> List[Dict]:
        """
        知识推理 - 遍历知识图谱
        返回从起点出发的可达节点路径
        """
        if start_node_id not in self._nodes:
            return []
        
        visited = set()
        queue = [(start_node_id, 0, [start_node_id])]
        inferences = []
        
        while queue:
            node_id, depth, path = queue.pop(0)
            
            if node_id in visited or depth > max_hops:
                continue
            
            visited.add(node_id)
            node = self._nodes[node_id]
            
            # 类型过滤
            if target_node_type and node.node_type != target_node_type and depth > 0:
                continue
            
            inferences.append({
                'node_id': node_id,
                'content': node.content,
                'node_type': node.node_type,
                'depth': depth,
                'path': path,
                'activation': node.activation
            })
            
            # 遍历连接（按权重排序）
            sorted_connections = sorted(
                node.connections.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            for neighbor_id, weight in sorted_connections:
                if neighbor_id not in visited:
                    queue.append((neighbor_id, depth + 1, path + [neighbor_id]))
        
        return inferences
    
    def connect_nodes(
        self,
        node_id1: str,
        node_id2: str,
        weight: float = 0.5,
        bidirectional: bool = True
    ):
        """连接两个节点"""
        if node_id1 in self._nodes and node_id2 in self._nodes:
            self._nodes[node_id1].connections[node_id2] = weight
            
            if bidirectional:
                self._nodes[node_id2].connections[node_id1] = weight
            
            self._save_node(self._nodes[node_id1])
            if bidirectional:
                self._save_node(self._nodes[node_id2])
            
            logger.debug(f"Connected nodes: {node_id1} <-> {node_id2} (weight: {weight})")
    
    def strengthen_connection(self, node_id1: str, node_id2: str, delta: float = 0.1):
        """增强节点间的连接权重（Hebbian学习）"""
        if node_id1 in self._nodes and node_id2 in self._nodes:
            current_weight = self._nodes[node_id1].connections.get(node_id2, 0.5)
            new_weight = min(1.0, current_weight + delta)
            self.connect_nodes(node_id1, node_id2, new_weight)
    
    def get_node(self, node_id: str) -> Optional[SemanticNode]:
        """获取单个节点"""
        return self._nodes.get(node_id)
    
    def delete_node(self, node_id: str) -> bool:
        """删除节点"""
        if node_id in self._nodes:
            # 从其他节点的连接中移除
            for node in self._nodes.values():
                if node_id in node.connections:
                    del node.connections[node_id]
                    self._save_node(node)
            
            # 从类型索引中移除
            node = self._nodes[node_id]
            if node.node_type in self._type_index and node_id in self._type_index[node.node_type]:
                self._type_index[node.node_type].remove(node_id)
            
            # 删除文件
            file_path = self.storage_path / f"{node_id}.json"
            if file_path.exists():
                file_path.unlink()
            
            del self._nodes[node_id]
            self._invalidate_embedding_cache()
            
            logger.info(f"Deleted node: {node_id}")
            return True
        return False
    
    def get_nodes_by_type(self, node_type: str) -> List[SemanticNode]:
        """按类型获取节点"""
        if node_type not in self._type_index:
            return []
        return [self._nodes[node_id] for node_id in self._type_index[node_type] if node_id in self._nodes]
    
    def get_graph_summary(self) -> Dict:
        """获取图谱摘要"""
        type_counts = {}
        total_connections = 0
        
        for node in self._nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1
            total_connections += len(node.connections)
        
        return {
            'total_nodes': len(self._nodes),
            'total_connections': total_connections // 2,  # 双向连接算一条
            'node_types': type_counts,
            'avg_connections': total_connections / len(self._nodes) if self._nodes else 0
        }
    
    def get_all_nodes(self) -> List[Dict]:
        """获取所有节点（用于UI显示）"""
        return [
            {
                'node_id': node.node_id,
                'content': node.content[:100] + "..." if len(node.content) > 100 else node.content,
                'node_type': node.node_type,
                'connections': list(node.connections.keys()),
                'connection_count': len(node.connections),
                'activation': round(node.activation, 3)
            }
            for node in self._nodes.values()
        ]
    
    def activate_node(self, node_id: str, activation: float = 0.5):
        """激活节点（传播激活）"""
        if node_id in self._nodes:
            self._nodes[node_id].activation = activation
            
            # 传播激活到连接的节点
            for neighbor_id, weight in self._nodes[node_id].connections.items():
                if neighbor_id in self._nodes:
                    self._nodes[neighbor_id].activation += activation * weight * 0.5
    
    def _embed(self, text: str) -> List[float]:
        """生成文本嵌入（使用简单的字符级哈希嵌入作为默认实现）"""
        try:
            # 尝试使用sentence-transformers（如果可用）
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            return model.encode(text).tolist()
        except ImportError:
            # 回退到简单的哈希嵌入
            import hashlib
            md5 = hashlib.md5(text.encode()).digest()
            embedding = []
            for byte in md5:
                embedding.append(byte / 255.0)
                embedding.append(byte / 255.0)
            
            # 归一化
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = [x / norm for x in embedding]
            
            return embedding
    
    def _build_embedding_cache(self):
        """构建嵌入矩阵缓存"""
        self._node_id_list = []
        embeddings = []
        
        for node_id, node in self._nodes.items():
            if node.embedding is not None:
                self._node_id_list.append(node_id)
                embeddings.append(node.embedding)
        
        if embeddings:
            self._embedding_matrix = np.array(embeddings)
    
    def _invalidate_embedding_cache(self):
        """使嵌入缓存失效"""
        self._embedding_matrix = None
        self._node_id_list = []
    
    def _build_type_index(self):
        """构建类型索引"""
        self._type_index.clear()
        for node_id, node in self._nodes.items():
            if node.node_type not in self._type_index:
                self._type_index[node.node_type] = []
            self._type_index[node.node_type].append(node_id)
    
    def _update_type_index(self, node: SemanticNode):
        """更新类型索引"""
        if node.node_type not in self._type_index:
            self._type_index[node.node_type] = []
        if node.node_id not in self._type_index[node.node_type]:
            self._type_index[node.node_type].append(node.node_id)
    
    def _save_node(self, node: SemanticNode):
        """保存节点"""
        file_path = self.storage_path / f"{node.node_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(node.to_dict(), f)
    
    def _load_nodes(self):
        """加载节点"""
        if not self.storage_path.exists():
            return
        
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    node = SemanticNode.from_dict(data)
                    self._nodes[node.node_id] = node
            except Exception as e:
                logger.error(f"Load node error: {e}")