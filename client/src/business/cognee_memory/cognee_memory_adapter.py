"""
Cognee 记忆增强适配器 (Cognee Memory Adapter)
遵循自我进化原则：从交互中学习记忆结构，而非预置固定结构

架构指南参考: docs/LIVINGTREE_ARCHITECTURE_GUIDE.md (章节 5.3.1)

实现 cognee 的核心 API：
- remember(text, session_id) -> 存储记忆
- recall(query, session_id) -> 召回记忆
- forget(session_id, memory_id) -> 遗忘记忆
- improve(feedback) -> 从反馈中改进
"""
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging
from datetime import datetime

from business.global_model_router import GlobalModelRouter, ModelCapability
from business.knowledge_graph.knowledge_graph_builder import KnowledgeGraphBuilder
from business.fusion_rag.vector_store import VectorStore


logger = logging.getLogger(__name__)


@dataclass
class Memory:
    """记忆数据结构 - 从交互中学习结构"""
    id: str
    text: str
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relations: List[Dict[str, Any]] = field(default_factory=list)
    session_id: str = ""
    timestamp: str = ""
    access_count: int = 0
    last_accessed: str = ""
    importance_score: float = 0.5  # 从交互中学习重要性
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "entities": self.entities,
            "relations": self.relations,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "importance_score": self.importance_score
        }


@dataclass
class RecallResult:
    """召回结果"""
    memories: List[Memory]
    query: str
    total_count: int
    recall_time_ms: float


class CogneeMemoryAdapter:
    """
    Cognee 记忆增强适配器

    核心原则：
    ❌ 不预置固定的记忆结构
    ✅ 自动从文本中提取实体和关系
    ✅ 存储到知识图谱 + 向量数据库
    ✅ 从访问模式中学习重要性分数
    ✅ 混合排序（向量 + 图谱 + 访问频率）
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        kg_builder: Optional[KnowledgeGraphBuilder] = None,
        vector_store: Optional[VectorStore] = None
    ):
        self.router = GlobalModelRouter()
        self.storage_path = storage_path or Path.home() / ".livingtree" / "cognee_memories.json"
        self.kg_builder = kg_builder or KnowledgeGraphBuilder()
        self.vector_store = vector_store or VectorStore()

        self.memories: Dict[str, Memory] = {}
        self.session_memories: Dict[str, List[str]] = {}  # session_id -> [memory_ids]
        self.access_patterns: Dict[str, Dict[str, int]] = {}  # session_id -> {memory_id: count}

        self._load_memories()

    def _load_memories(self):
        """加载已存储的记忆"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for mem_data in data.get("memories", []):
                        memory = Memory(**mem_data)
                        self.memories[memory.id] = memory

                    self.session_memories = data.get("session_memories", {})
                    self.access_patterns = data.get("access_patterns", {})

                logger.info(f"✅ 已加载 {len(self.memories)} 条记忆")
            except Exception as e:
                logger.warning(f"⚠️ 加载记忆失败: {e}")

    def _save_memories(self):
        """保存记忆"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "memories": [m.to_dict() for m in self.memories.values()],
                "session_memories": self.session_memories,
                "access_patterns": self.access_patterns
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存记忆失败: {e}")

    async def remember(self, text: str, session_id: Optional[str] = None) -> Memory:
        """
        存储记忆

        流程：
        1. 自动提取实体和关系（使用 LLM）
        2. 存储到知识图谱
        3. 存储到向量数据库
        4. 返回 Memory 对象
        """
        logger.info(f"🧠 存储记忆: {text[:50]}...")

        # 1. 提取实体和关系
        entities, relations = await self._extract_entities_and_relations(text)

        # 2. 创建记忆对象
        memory_id = f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.memories)}"
        memory = Memory(
            id=memory_id,
            text=text,
            entities=entities,
            relations=relations,
            session_id=session_id or "default",
            timestamp=datetime.now().isoformat(),
            importance_score=0.5  # 初始重要性
        )

        # 3. 存储到知识图谱
        try:
            await self.kg_builder.add_entities_and_relations(entities, relations)
        except Exception as e:
            logger.warning(f"⚠️ 知识图谱存储失败: {e}")

        # 4. 存储到向量数据库
        try:
            embedding = await self._get_embedding(text)
            memory.embedding = embedding
            await self.vector_store.upsert(memory_id, embedding, memory.to_dict())
        except Exception as e:
            logger.warning(f"⚠️ 向量存储失败: {e}")

        # 5. 保存到内存和磁盘
        self.memories[memory_id] = memory
        if session_id:
            if session_id not in self.session_memories:
                self.session_memories[session_id] = []
            self.session_memories[session_id].append(memory_id)

        self._save_memories()
        logger.info(f"✅ 记忆已存储: {memory_id}")

        return memory

    async def recall(self, query: str, session_id: Optional[str] = None, top_k: int = 5) -> RecallResult:
        """
        召回记忆

        流程：
        1. 向量搜索（语义相似）
        2. 知识图谱推理（关联记忆）
        3. 混合排序（向量分数 + 图谱分数 + 访问频率）
        4. 返回排序后的记忆
        """
        logger.info(f"🔍 召回记忆: {query[:50]}...")
        start_time = datetime.now()

        # 1. 向量搜索
        vector_results = await self._vector_search(query, top_k * 2)

        # 2. 知识图谱推理
        kg_results = await self._kg_reasoning(query, session_id)

        # 3. 合并和去重
        all_memories = self._merge_and_dedup(vector_results, kg_results)

        # 4. 混合排序
        ranked = self._hybrid_rank(all_memories, query, session_id)

        # 5. 更新访问计数
        for memory in ranked[:top_k]:
            memory.access_count += 1
            memory.last_accessed = datetime.now().isoformat()
            if session_id:
                if session_id not in self.access_patterns:
                    self.access_patterns[session_id] = {}
                self.access_patterns[session_id][memory.id] = self.access_patterns[session_id].get(memory.id, 0) + 1

        # 6. 学习重要性分数
        await self._learn_importance(ranked[:top_k], query)

        self._save_memories()

        recall_time = (datetime.now() - start_time).total_seconds() * 1000
        return RecallResult(
            memories=ranked[:top_k],
            query=query,
            total_count=len(all_memories),
            recall_time_ms=recall_time
        )

    async def forget(self, session_id: str, memory_id: Optional[str] = None) -> int:
        """
        遗忘记忆

        如果指定 memory_id，遗忘特定记忆
        否则遗忘整个 session 的记忆
        返回遗忘的记忆数量
        """
        if memory_id:
            # 遗忘特定记忆
            if memory_id in self.memories:
                del self.memories[memory_id]
                logger.info(f"🗑️ 已遗忘记忆: {memory_id}")
                self._save_memories()
                return 1
            return 0

        # 遗忘 session 的所有记忆
        if session_id in self.session_memories:
            memory_ids = self.session_memories[session_id]
            for mid in memory_ids:
                if mid in self.memories:
                    del self.memories[mid]
            del self.session_memories[session_id]
            logger.info(f"🗑️ 已遗忘 session {session_id} 的 {len(memory_ids)} 条记忆")
            self._save_memories()
            return len(memory_ids)

        return 0

    async def improve(self, feedback: Dict[str, Any]):
        """
        从反馈中改进

        反馈格式:
        {
            "query": "原始查询",
            "recalled_memories": [memory_id1, memory_id2, ...],
            "useful_memories": [memory_id1, ...],  # 用户标记的有用记忆
            "rating": 0.8  # 召回质量评分 0-1
        }
        """
        query = feedback.get("query", "")
        useful_ids = feedback.get("useful_memories", [])
        rating = feedback.get("rating", 0.5)

        # 更新有用记忆的重要性分数
        for mid in useful_ids:
            if mid in self.memories:
                memory = self.memories[mid]
                # 重要性分数向评分靠拢
                memory.importance_score = memory.importance_score * 0.7 + rating * 0.3

        # 记录反馈到访问模式
        session_id = feedback.get("session_id", "default")
        if session_id not in self.access_patterns:
            self.access_patterns[session_id] = {}

        for mid in useful_ids:
            self.access_patterns[session_id][mid] = self.access_patterns[session_id].get(mid, 0) + 2  # 有用记忆加权

        self._save_memories()
        logger.info(f"📈 已从反馈中改进: 有用记忆 {len(useful_ids)} 条")

    async def _extract_entities_and_relations(self, text: str) -> tuple:
        """使用 LLM 提取实体和关系"""
        prompt = f"""
作为一个知识图谱构建专家，从以下文本中提取实体和关系。

文本: {text}

要求：
1. 识别所有关键实体（人物、地点、组织、概念等）
2. 识别实体间的关系
3. 返回 JSON 格式

返回格式:
{{
    "entities": [
        {{"id": "e1", "type": "人物", "name": "张三", "properties": {{}}}},
        ...
    ],
    "relations": [
        {{"source": "e1", "target": "e2", "type": "工作于", "properties": {{}}}},
        ...
    ]
}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.1
            )
            result = json.loads(response)
            return result.get("entities", []), result.get("relations", [])
        except Exception as e:
            logger.error(f"❌ 提取实体关系失败: {e}")
            return [], []

    async def _get_embedding(self, text: str) -> List[float]:
        """获取文本的向量嵌入"""
        # 使用 Ollama embeddings API
        try:
            import requests
            response = requests.post(
                "http://localhost:11434/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text}
            )
            return response.json().get("embedding", [])
        except Exception as e:
            logger.error(f"❌ 获取嵌入失败: {e}")
            return []

    async def _vector_search(self, query: str, top_k: int) -> List[Memory]:
        """向量搜索"""
        try:
            query_embedding = await self._get_embedding(query)
            results = await self.vector_store.search(query_embedding, top_k)

            memories = []
            for r in results:
                memory_id = r.get("id")
                if memory_id in self.memories:
                    memories.append(self.memories[memory_id])
            return memories
        except Exception as e:
            logger.warning(f"⚠️ 向量搜索失败: {e}")
            return []

    async def _kg_reasoning(self, query: str, session_id: Optional[str]) -> List[Memory]:
        """知识图谱推理"""
        try:
            # 从查询中提取关键实体
            entities, _ = await self._extract_entities_and_relations(query)

            # 查询知识图谱
            related_memories = []
            for entity in entities:
                entity_id = entity.get("id")
                related = await self.kg_builder.query_related(entity_id)
                for r in related:
                    memory_id = r.get("memory_id")
                    if memory_id in self.memories and memory_id not in [m.id for m in related_memories]:
                        related_memories.append(self.memories[memory_id])

            return related_memories
        except Exception as e:
            logger.warning(f"⚠️ 知识图谱推理失败: {e}")
            return []

    def _merge_and_dedup(self, list1: List[Memory], list2: List[Memory]) -> List[Memory]:
        """合并和去重"""
        merged = {m.id: m for m in list1}
        for m in list2:
            if m.id not in merged:
                merged[m.id] = m
        return list(merged.values())

    def _hybrid_rank(self, memories: List[Memory], query: str, session_id: Optional[str]) -> List[Memory]:
        """
        混合排序

        综合考虑：
        1. 向量相似度（已在 vector_results 中）
        2. 知识图谱关联度（已在 kg_results 中）
        3. 访问频率（access_count）
        4. 近期性（last_accessed）
        5. 重要性分数（importance_score）
        """
        def _score(m: Memory) -> float:
            # 访问频率分数（归一化）
            access_score = min(m.access_count / 10.0, 1.0)

            # 近期性分数
            recency_score = 0.5  # 默认
            if m.last_accessed:
                try:
                    from datetime import datetime
                    last = datetime.fromisoformat(m.last_accessed)
                    now = datetime.now()
                    days_ago = (now - last).days
                    recency_score = 1.0 / (1.0 + days_ago)
                except Exception:
                    pass

            # 重要性分数
            importance_score = m.importance_score

            # 综合分数
            return access_score * 0.3 + recency_score * 0.2 + importance_score * 0.5

        return sorted(memories, key=_score, reverse=True)

    async def _learn_importance(self, memories: List[Memory], query: str):
        """从查询中学习记忆的重要性"""
        for memory in memories:
            # 如果记忆被召回，重要性略微提升
            memory.importance_score = min(memory.importance_score * 1.05, 1.0)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.memories:
            return {"total_memories": 0}

        total_access = sum(m.access_count for m in self.memories.values())
        avg_importance = sum(m.importance_score for m in self.memories.values()) / len(self.memories)

        return {
            "total_memories": len(self.memories),
            "total_sessions": len(self.session_memories),
            "total_access_count": total_access,
            "average_importance": round(avg_importance, 2),
            "top_memories": [
                {
                    "id": m.id,
                    "text": m.text[:50],
                    "access_count": m.access_count,
                    "importance": round(m.importance_score, 2)
                }
                for m in sorted(self.memories.values(), key=lambda x: x.importance_score, reverse=True)[:5]
            ]
        }
