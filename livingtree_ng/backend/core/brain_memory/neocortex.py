"""
新皮层模块 - 语义记忆与推理
借鉴大脑新皮层的工作原理
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SemanticNode:
    """语义节点"""
    node_id: str
    content: str
    node_type: str
    embedding: Optional[List[float]] = None
    connections: Dict[str, float] = None
    metadata: Dict[str, Any] = None
    
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
            'metadata': self.metadata
        }


class Neocortex:
    """
    新皮层 - 长期语义记忆存储
    负责知识推理和关联
    """
    
    def __init__(self, storage_path: str = "data/memory/neocortex"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._nodes: Dict[str, SemanticNode] = {}
        self._load_nodes()
        
    def store_semantic(
        self,
        content: str,
        node_type: str = "concept",
        metadata: Optional[Dict] = None
    ) -> str:
        """存储语义知识"""
        import uuid
        node_id = str(uuid.uuid4())
        
        node = SemanticNode(
            node_id=node_id,
            content=content,
            node_type=node_type,
            embedding=self._embed(content),
            metadata=metadata or {}
        )
        
        self._nodes[node_id] = node
        self._save_node(node)
        
        logger.debug(f"Stored semantic node: {node_id}")
        return node_id
    
    def retrieve_semantic(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict]:
        """语义检索"""
        if not self._nodes:
            return []
        
        query_embedding = self._embed(query)
        
        # 计算相似度
        results = []
        for node_id, node in self._nodes.items():
            if node.embedding is not None:
                similarity = self._cosine_similarity(query_embedding, node.embedding)
                results.append({
                    'node_id': node_id,
                    'content': node.content,
                    'node_type': node.node_type,
                    'similarity': similarity,
                    'metadata': node.metadata
                })
        
        # 排序
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:limit]
    
    def make_inference(
        self,
        start_node_id: str,
        max_hops: int = 3
    ) -> List[Dict]:
        """知识推理 - 遍历知识图谱"""
        if start_node_id not in self._nodes:
            return []
        
        visited = set()
        queue = [(start_node_id, 0)]
        inferences = []
        
        while queue:
            node_id, depth = queue.pop(0)
            
            if node_id in visited or depth > max_hops:
                continue
            
            visited.add(node_id)
            node = self._nodes[node_id]
            
            inferences.append({
                'node_id': node_id,
                'content': node.content,
                'depth': depth
            })
            
            # 遍历连接
            for neighbor_id, weight in node.connections.items():
                if neighbor_id not in visited:
                    queue.append((neighbor_id, depth + 1))
        
        return inferences
    
    def connect_nodes(
        self,
        node_id1: str,
        node_id2: str,
        weight: float = 0.5
    ):
        """连接两个节点"""
        if node_id1 in self._nodes and node_id2 in self._nodes:
            self._nodes[node_id1].connections[node_id2] = weight
            self._nodes[node_id2].connections[node_id1] = weight
            self._save_node(self._nodes[node_id1])
            self._save_node(self._nodes[node_id2])
    
    def _embed(self, text: str) -> List[float]:
        """简单的嵌入（实际可用sentence-transformers）"""
        # 简单的字符级嵌入（占位）
        import hashlib
        md5 = hashlib.md5(text.encode()).digest()
        
        # 转为浮点数数组
        embedding = []
        for byte in md5:
            embedding.append(byte / 255.0)
            embedding.append(byte / 255.0)  # 扩展到32维
        
        # 归一化
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """余弦相似度"""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
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
                    node = SemanticNode(**data)
                    self._nodes[node.node_id] = node
            except Exception as e:
                logger.error(f"Load node error: {e}")
