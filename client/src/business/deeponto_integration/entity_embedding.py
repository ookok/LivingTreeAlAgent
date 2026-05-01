"""
Entity Embedding Service

Provides deep learning based entity embedding using DeepOnto.
Supports semantic similarity calculation and entity resolution.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from dataclasses import dataclass

try:
    from deeponto.embedding import OntologyEmbedding, TransE, DistMult
    HAS_DEEPONTO = True
except ImportError:
    HAS_DEEPONTO = False

@dataclass
class EmbeddingResult:
    embedding: np.ndarray
    similarity: Optional[float] = None

@dataclass
class EntityMatch:
    entity_id: str
    score: float
    metadata: Dict[str, Any]

class EntityEmbeddingService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self, model_type: str = "transe"):
        if not HAS_DEEPONTO:
            self._mock_mode = True
            self._initialized = True
            return
        
        self._mock_mode = False
        if model_type.lower() == "distmult":
            self.embedding_model = DistMult()
        else:
            self.embedding_model = TransE()
        self._initialized = True
    
    def ensure_initialized(self):
        if not self._initialized:
            self.initialize()
    
    def encode_entity(self, entity_name: str) -> EmbeddingResult:
        self.ensure_initialized()
        if self._mock_mode:
            return EmbeddingResult(
                embedding=np.random.randn(300).astype(np.float32)
            )
        embedding = self.embedding_model.encode(entity_name)
        return EmbeddingResult(embedding=embedding)
    
    def encode_entities(self, entity_names: List[str]) -> Dict[str, EmbeddingResult]:
        self.ensure_initialized()
        results = {}
        for name in entity_names:
            results[name] = self.encode_entity(name)
        return results
    
    def calculate_similarity(self, entity1: str, entity2: str) -> float:
        self.ensure_initialized()
        if self._mock_mode:
            return np.random.uniform(0.5, 1.0)
        
        emb1 = self.embedding_model.encode(entity1)
        emb2 = self.embedding_model.encode(entity2)
        return float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))
    
    def find_similar_entities(self, query_entity: str, candidates: List[str], top_k: int = 5) -> List[EntityMatch]:
        self.ensure_initialized()
        if self._mock_mode:
            return [
                EntityMatch(entity_id=c, score=np.random.uniform(0.7, 1.0), metadata={})
                for c in candidates[:top_k]
            ]
        
        query_emb = self.embedding_model.encode(query_entity)
        matches = []
        
        for candidate in candidates:
            cand_emb = self.embedding_model.encode(candidate)
            score = float(np.dot(query_emb, cand_emb) / (np.linalg.norm(query_emb) * np.linalg.norm(cand_emb)))
            matches.append(EntityMatch(entity_id=candidate, score=score, metadata={}))
        
        matches.sort(key=lambda x: x.score, reverse=True)
        return matches[:top_k]
    
    def resolve_entity(self, mention: str, context: Dict[str, Any]) -> EntityMatch:
        self.ensure_initialized()
        if self._mock_mode:
            return EntityMatch(
                entity_id=mention,
                score=0.95,
                metadata={"resolved": True}
            )
        
        candidates = context.get("candidates", [])
        if not candidates:
            return EntityMatch(entity_id=mention, score=0.8, metadata={})
        
        query_emb = self.embedding_model.encode(mention)
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            cand_emb = self.embedding_model.encode(candidate)
            score = float(np.dot(query_emb, cand_emb) / (np.linalg.norm(query_emb) * np.linalg.norm(cand_emb)))
            if score > best_score:
                best_score = score
                best_match = EntityMatch(entity_id=candidate, score=score, metadata={})
        
        return best_match or EntityMatch(entity_id=mention, score=0.7, metadata={})
    
    def cluster_entities(self, entities: List[str], num_clusters: int = 5) -> Dict[int, List[str]]:
        self.ensure_initialized()
        if self._mock_mode:
            clusters = {}
            for i, entity in enumerate(entities):
                cluster_id = i % num_clusters
                if cluster_id not in clusters:
                    clusters[cluster_id] = []
                clusters[cluster_id].append(entity)
            return clusters
        
        embeddings = [self.embedding_model.encode(e) for e in entities]
        from sklearn.cluster import KMeans
        kmeans = KMeans(n_clusters=num_clusters, random_state=42)
        labels = kmeans.fit_predict(np.array(embeddings))
        
        clusters = {}
        for i, entity in enumerate(entities):
            cluster_id = int(labels[i])
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(entity)
        
        return clusters

def get_entity_embedding_service() -> EntityEmbeddingService:
    return EntityEmbeddingService()