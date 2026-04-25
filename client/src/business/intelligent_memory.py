"""
智能记忆系统
Intelligent Memory System

核心功能：
1. 语义缓存 - 保存历史问答，支持相似问题复用
2. 事实锚点 - 从对话中提取实体和事实，消除幻觉
3. 上下文示例 - 为新问题检索高质量历史问答作为 Few-Shot
4. 知识图谱 - 存储实体关系，支持精准检索

设计原则：
- 漏斗筛选：只存高价值信息
- 结构化存储：实体、关系、问答分开存储
- 混合检索：关键词 + 语义向量
"""

import json
import time
import hashlib
import sqlite3
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading
import re


class MemoryValue(Enum):
    """记忆价值等级"""
    LOW = 0       # 噪音信息
    MEDIUM = 1   # 一般信息
    HIGH = 2     # 重要事实
    CRITICAL = 3 # 核心知识


@dataclass
class Fact:
    """结构化事实"""
    id: str = ""
    subject: str = ""       # 主语
    predicate: str = ""     # 谓语
    object: str = ""        # 宾语
    context: str = ""       # 上下文
    confidence: float = 1.0 # 置信度
    source: str = ""        # 来源
    created_at: float = field(default_factory=time.time)
    last_verified: float = field(default_factory=time.time)
    value_level: int = MemoryValue.HIGH.value


@dataclass
class QAPair:
    """问答对"""
    id: str = ""
    question: str = ""
    answer: str = ""
    question_embedding: str = ""  # 简化：用关键词hash代替向量
    question_keywords: List[str] = field(default_factory=list)
    answer_entities: List[str] = field(default_factory=list)
    quality_score: float = 1.0    # 质量评分
    usage_count: int = 0          # 使用次数
    last_used: float = 0
    created_at: float = field(default_factory=time.time)
    is_verified: bool = False      # 是否经过人工验证
    tags: List[str] = field(default_factory=list)


@dataclass
class Entity:
    """实体"""
    id: str = ""
    name: str = ""
    entity_type: str = ""   # person/organization/concept/event
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)


@dataclass
class Relation:
    """关系"""
    id: str = ""
    source_id: str = ""     # 源实体ID
    target_id: str = ""     # 目标实体ID
    relation_type: str = "" # 关系类型
    confidence: float = 1.0
    context: str = ""
    created_at: float = field(default_factory=time.time)


class MemoryDatabase:
    """记忆数据库"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript("""
                -- 问答对表
                CREATE TABLE IF NOT EXISTS qa_pairs (
                    id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    question_keywords TEXT DEFAULT '[]',
                    answer_entities TEXT DEFAULT '[]',
                    quality_score REAL DEFAULT 1.0,
                    usage_count INTEGER DEFAULT 0,
                    last_used REAL DEFAULT 0,
                    created_at REAL DEFAULT 0,
                    is_verified INTEGER DEFAULT 0,
                    tags TEXT DEFAULT '[]'
                );

                -- 实体表
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    entity_type TEXT DEFAULT '',
                    aliases TEXT DEFAULT '[]',
                    description TEXT DEFAULT '',
                    attributes TEXT DEFAULT '{}',
                    confidence REAL DEFAULT 1.0,
                    created_at REAL DEFAULT 0,
                    last_updated REAL DEFAULT 0
                );

                -- 关系表
                CREATE TABLE IF NOT EXISTS relations (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    context TEXT DEFAULT '',
                    created_at REAL DEFAULT 0,
                    FOREIGN KEY (source_id) REFERENCES entities(id),
                    FOREIGN KEY (target_id) REFERENCES entities(id)
                );

                -- 事实表
                CREATE TABLE IF NOT EXISTS facts (
                    id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    context TEXT DEFAULT '',
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT '',
                    created_at REAL DEFAULT 0,
                    last_verified REAL DEFAULT 0,
                    value_level INTEGER DEFAULT 2
                );

                -- 用户偏好表
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    updated_at REAL DEFAULT 0
                );

                -- 索引
                CREATE INDEX IF NOT EXISTS idx_qa_question ON qa_pairs(question);
                CREATE INDEX IF NOT EXISTS idx_qa_created ON qa_pairs(created_at);
                CREATE INDEX IF NOT EXISTS idx_qa_usage ON qa_pairs(usage_count DESC);
                CREATE INDEX IF NOT EXISTS idx_entity_name ON entities(name);
                CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject);
                CREATE INDEX IF NOT EXISTS idx_facts_predicate ON facts(predicate);
                CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
                CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _generate_id(self, *parts: str) -> str:
        """生成唯一ID"""
        raw = "|".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    # === 问答对操作 ===

    def save_qa_pair(self, qa: QAPair) -> str:
        """保存问答对"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                if not qa.id:
                    qa.id = self._generate_id(qa.question, qa.answer[:50])

                conn.execute("""
                    INSERT OR REPLACE INTO qa_pairs 
                    (id, question, answer, question_keywords, answer_entities,
                     quality_score, usage_count, last_used, created_at, is_verified, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    qa.id, qa.question, qa.answer,
                    json.dumps(qa.question_keywords),
                    json.dumps(qa.answer_entities),
                    qa.quality_score, qa.usage_count, qa.last_used,
                    qa.created_at, int(qa.is_verified),
                    json.dumps(qa.tags)
                ))
                conn.commit()
                return qa.id
            finally:
                conn.close()

    def search_qa_pairs(
        self, 
        keywords: List[str],
        limit: int = 5,
        min_quality: float = 0.5
    ) -> List[QAPair]:
        """搜索相似问答对"""
        if not keywords:
            return []

        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                # 构建搜索条件
                conditions = " OR ".join(
                    "question_keywords LIKE ?" for _ in keywords
                )
                params = [f"%{kw}%" for kw in keywords]
                params.append(min_quality)

                rows = conn.execute(f"""
                    SELECT * FROM qa_pairs 
                    WHERE ({conditions}) AND quality_score >= ?
                    ORDER BY (quality_score * usage_count + 1) DESC
                    LIMIT ?
                """, (*params, limit)).fetchall()

                return [self._row_to_qa(row) for row in rows]
            finally:
                conn.close()

    def get_fact_anchors(self, topic: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取事实锚点"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                rows = conn.execute("""
                    SELECT * FROM facts 
                    WHERE subject LIKE ? OR object LIKE ?
                    ORDER BY confidence DESC, value_level DESC
                    LIMIT ?
                """, (f"%{topic}%", f"%{topic}%", limit)).fetchall()

                return [{
                    "subject": r[1],
                    "predicate": r[2],
                    "object": r[3],
                    "context": r[4],
                    "confidence": r[5],
                    "source": r[6]
                } for r in rows]
            finally:
                conn.close()

    def increment_qa_usage(self, qa_id: str):
        """增加使用次数"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    UPDATE qa_pairs 
                    SET usage_count = usage_count + 1, last_used = ?
                    WHERE id = ?
                """, (time.time(), qa_id))
                conn.commit()
            finally:
                conn.close()

    def update_qa_quality(self, qa_id: str, quality_delta: float):
        """更新质量评分"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    UPDATE qa_pairs 
                    SET quality_score = MAX(0.0, MIN(1.0, quality_score + ?))
                    WHERE id = ?
                """, (quality_delta, qa_id))
                conn.commit()
            finally:
                conn.close()

    # === 实体操作 ===

    def save_entity(self, entity: Entity) -> str:
        """保存实体"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                if not entity.id:
                    entity.id = self._generate_id(entity.name, entity.entity_type)

                conn.execute("""
                    INSERT OR REPLACE INTO entities 
                    (id, name, entity_type, aliases, description, attributes, 
                     confidence, created_at, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entity.id, entity.name, entity.entity_type,
                    json.dumps(entity.aliases), entity.description,
                    json.dumps(entity.attributes), entity.confidence,
                    entity.created_at, entity.last_updated
                ))
                conn.commit()
                return entity.id
            finally:
                conn.close()

    def get_entity(self, name: str) -> Optional[Entity]:
        """获取实体"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                row = conn.execute(
                    "SELECT * FROM entities WHERE name = ? OR aliases LIKE ?",
                    (name, f"%{name}%")
                ).fetchone()
                return self._row_to_entity(row) if row else None
            finally:
                conn.close()

    # === 关系操作 ===

    def save_relation(self, relation: Relation) -> str:
        """保存关系"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                if not relation.id:
                    relation.id = self._generate_id(
                        relation.source_id, relation.relation_type, relation.target_id
                    )

                conn.execute("""
                    INSERT OR REPLACE INTO relations 
                    (id, source_id, target_id, relation_type, confidence, context, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    relation.id, relation.source_id, relation.target_id,
                    relation.relation_type, relation.confidence,
                    relation.context, relation.created_at
                ))
                conn.commit()
                return relation.id
            finally:
                conn.close()

    # === 用户偏好 ===

    def set_preference(self, key: str, value: str, category: str = "general"):
        """设置用户偏好"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO user_preferences (key, value, category, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (key, value, category, time.time()))
                conn.commit()
            finally:
                conn.close()

    def get_preference(self, key: str, default: str = "") -> str:
        """获取用户偏好"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                row = conn.execute(
                    "SELECT value FROM user_preferences WHERE key = ?",
                    (key,)
                ).fetchone()
                return row[0] if row else default
            finally:
                conn.close()

    def get_preferences_by_category(self, category: str) -> Dict[str, str]:
        """获取分类偏好"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                rows = conn.execute(
                    "SELECT key, value FROM user_preferences WHERE category = ?",
                    (category,)
                ).fetchall()
                return {r[0]: r[1] for r in rows}
            finally:
                conn.close()

    # === 辅助方法 ===

    def _row_to_qa(self, row: sqlite3.Row) -> QAPair:
        return QAPair(
            id=row[0], question=row[1], answer=row[2],
            question_keywords=json.loads(row[3] or "[]"),
            answer_entities=json.loads(row[4] or "[]"),
            quality_score=row[5], usage_count=row[6],
            last_used=row[7], created_at=row[8],
            is_verified=bool(row[9]),
            tags=json.loads(row[10] or "[]")
        )

    def _row_to_entity(self, row: sqlite3.Row) -> Entity:
        return Entity(
            id=row[0], name=row[1], entity_type=row[2],
            aliases=json.loads(row[3] or "[]"),
            description=row[4],
            attributes=json.loads(row[5] or "{}"),
            confidence=row[6],
            created_at=row[7], last_updated=row[8]
        )

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                return {
                    "qa_pairs": conn.execute("SELECT COUNT(*) FROM qa_pairs").fetchone()[0],
                    "entities": conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
                    "relations": conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0],
                    "facts": conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0],
                }
            finally:
                conn.close()


class MemoryFilter:
    """记忆过滤器 - 评估信息价值"""

    # 高价值关键词
    HIGH_VALUE_PATTERNS = [
        r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}",  # 日期
        r"\d+[万千万亿]?元",  # 金额
        r"电话|手机|邮箱|地址|账号",  # 联系方式
        r"项目|产品|功能|版本|发布",  # 项目相关
        r"API|SDK|配置|参数|设置",  # 技术配置
        r"决策|策略|方案|计划|目标",  # 决策相关
    ]

    # 低价值关键词
    LOW_VALUE_PATTERNS = [
        r"^(你好|谢谢|是的|不是|可能|也许)",  # 简单寒暄
        r"^(哈哈|嗯嗯|好的)$",  # 敷衍回复
        r"^那|那好吧|随便",  # 无意义回应
    ]

    @classmethod
    def assess_value(cls, text: str) -> Tuple[MemoryValue, str]:
        """
        评估文本价值
        返回: (价值等级, 评估理由)
        """
        text_lower = text.lower()

        # 检查低价值模式
        for pattern in cls.LOW_VALUE_PATTERNS:
            if re.match(pattern, text.strip()):
                return MemoryValue.LOW, "简单寒暄/无意义回复"

        # 检查高价值模式
        for pattern in cls.HIGH_VALUE_PATTERNS:
            if re.search(pattern, text):
                return MemoryValue.HIGH, f"包含关键信息: {pattern}"

        # 检查实体
        if cls._contains_entity(text):
            return MemoryValue.MEDIUM, "包含实体信息"

        # 检查问题-答案对
        if "?" in text or "？" in text:
            return MemoryValue.MEDIUM, "包含问答内容"

        return MemoryValue.LOW, "一般性对话"

    @classmethod
    def _contains_entity(cls, text: str) -> bool:
        """简单实体检测"""
        # 实际上应该用NER，这里用关键词简化
        entity_markers = [
            "是", "叫做", "称为", "位于", "属于",
            "公司", "机构", "组织", "产品", "技术"
        ]
        return any(marker in text for marker in entity_markers)


class KnowledgeExtractor:
    """知识提取器 - 从对话中提取结构化知识"""

    # 实体类型模式
    ENTITY_PATTERNS = {
        "person": [r"([A-Z\u4e00-\u9fa5]{2,4})(?:说|认为|提出|发现|开发|创建)"],
        "organization": [r"([A-Z\u4e00-\u9fa5]+公司|([A-Z\u4e00-\u9fa5]+)机构|([A-Z\u4e00-\u9fa5]+)组织)"],
        "technology": [r"([A-Z][a-zA-Z]+(?:式|法|器|系统|平台))"],
    }

    # 关系类型
    RELATION_TYPES = [
        "是", "属于", "位于", "开发", "创建", "基于",
        "使用", "依赖", "包含", "替代", "优于", "劣于"
    ]

    @classmethod
    def extract_entities(cls, text: str) -> List[Entity]:
        """提取实体"""
        entities = []

        for entity_type, patterns in cls.ENTITY_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    name = match.group(1) if match.groups() else match.group(0)
                    if len(name) >= 2:
                        entities.append(Entity(
                            name=name,
                            entity_type=entity_type,
                            confidence=0.8
                        ))

        return entities

    @classmethod
    def extract_facts(cls, text: str, source: str = "") -> List[Fact]:
        """提取事实三元组"""
        facts = []

        # 简单的事实提取模式
        fact_patterns = [
            r"(.+?)是(.+)",  # A是B
            r"(.+?)属于(.+)",  # A属于B
            r"(.+?)位于(.+)",  # A位于B
            r"(.+?)使用(.+)",  # A使用B
        ]

        for pattern in fact_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                subject = match.group(1).strip()
                obj = match.group(2).strip()

                if len(subject) >= 2 and len(obj) >= 1:
                    predicate = match.group(0).split("是")[0] if "是" in match.group(0) else pattern.split("(")[1][0]

                    facts.append(Fact(
                        subject=subject,
                        predicate=predicate,
                        object=obj,
                        context=text[:200],
                        source=source,
                        value_level=MemoryValue.MEDIUM.value
                    ))

        return facts

    @classmethod
    def extract_keywords(cls, text: str, top_n: int = 10) -> List[str]:
        """提取关键词"""
        # 简单实现：去除停用词后取高频词
        stopwords = {
            "的", "是", "在", "有", "和", "与", "了", "我", "你", "他",
            "她", "它", "这", "那", "个", "一", "不", "也", "都", "要",
            "就", "可以", "会", "能", "对", "但", "而", "或", "如果"
        }

        # 分词（简单按标点和空格分）
        words = re.findall(r"[\u4e00-\u9fa5]+|[A-Za-z]+", text)

        # 过滤和计数
        word_freq = {}
        for word in words:
            if len(word) >= 2 and word not in stopwords:
                word_freq[word] = word_freq.get(word, 0) + 1

        # 排序取top
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:top_n]]


class IntelligentMemorySystem:
    """
    智能记忆系统

    功能：
    - 自动保存有价值的历史问答
    - 提取结构化事实作为"事实锚点"
    - 为新问题检索相似问答和事实
    - 动态构建 Few-Shot 示例
    """

    def __init__(self, db_path: str | Path = None):
        from client.src.business.config import get_config_dir

        if db_path is None:
            db_path = get_config_dir() / "intelligent_memory.db"

        self.db = MemoryDatabase(db_path)
        self.filter = MemoryFilter()
        self.extractor = KnowledgeExtractor()

        # 配置
        self.config = {
            "auto_save_qa": True,
            "auto_extract_facts": True,
            "max_context_examples": 3,
            "min_quality_for_fewshot": 0.6,
            "fact_anchor_limit": 5,
        }

    def record_interaction(
        self,
        question: str,
        answer: str,
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        记录一次交互

        Args:
            question: 用户问题
            answer: AI回答
            metadata: 附加元数据（如话题、标签等）

        Returns:
            问答对ID，如果被过滤则返回None
        """
        # 评估价值
        combined_text = f"{question} {answer}"
        value, reason = self.filter.assess_value(combined_text)

        # 低价值信息跳过
        if value == MemoryValue.LOW:
            return None

        # 提取关键词
        keywords = self.extractor.extract_keywords(combined_text)

        # 提取实体
        entities = self.extractor.extract_entities(combined_text)

        # 创建问答对
        qa = QAPair(
            question=question,
            answer=answer,
            question_keywords=keywords,
            answer_entities=[e.name for e in entities],
            quality_score=0.7 if value == MemoryValue.HIGH else 0.5,
            tags=metadata.get("tags", []) if metadata else []
        )

        # 保存
        qa_id = self.db.save_qa_pair(qa)

        # 提取并保存事实
        if value == MemoryValue.HIGH:
            facts = self.extractor.extract_facts(
                combined_text,
                source=f"qa:{qa_id}"
            )
            for fact in facts:
                self.db.save_qa_pair  # 复用ID生成逻辑
                # 保存到facts表（需要扩展数据库操作）

        # 保存实体
        for entity in entities:
            self.db.save_entity(entity)

        return qa_id

    def retrieve_context(
        self,
        query: str,
        max_fewshot: int = None,
        include_facts: bool = True
    ) -> Dict[str, Any]:
        """
        为新查询检索上下文

        Args:
            query: 用户问题
            max_fewshot: 最大示例数量
            include_facts: 是否包含事实锚点

        Returns:
            {
                "fewshot_examples": [...],  # 相似问答对
                "fact_anchors": [...],       # 事实锚点
                "entities": [...],           # 相关实体
            }
        """
        if max_fewshot is None:
            max_fewshot = self.config["max_context_examples"]

        # 提取查询关键词
        query_keywords = self.extractor.extract_keywords(query)

        # 检索相似问答
        similar_qa = self.db.search_qa_pairs(
            query_keywords,
            limit=max_fewshot,
            min_quality=self.config["min_quality_for_fewshot"]
        )

        # 更新使用次数
        for qa in similar_qa:
            self.db.increment_qa_usage(qa.id)

        # 获取事实锚点
        fact_anchors = []
        if include_facts:
            # 从查询中提取主题
            topic = query_keywords[0] if query_keywords else query[:20]
            fact_anchors = self.db.get_fact_anchors(topic, self.config["fact_anchor_limit"])

        # 获取相关实体
        entities = []
        for keyword in query_keywords[:3]:
            entity = self.db.get_entity(keyword)
            if entity:
                entities.append(entity)

        return {
            "fewshot_examples": [
                {"question": qa.question, "answer": qa.answer, "quality": qa.quality_score}
                for qa in similar_qa
            ],
            "fact_anchors": fact_anchors,
            "entities": [
                {"name": e.name, "type": e.entity_type, "description": e.description}
                for e in entities
            ],
            "query_keywords": query_keywords
        }

    def build_enhanced_prompt(
        self,
        original_prompt: str,
        query: str
    ) -> str:
        """
        构建增强提示词

        将检索到的上下文注入到原始提示词中
        """
        context = self.retrieve_context(query)

        parts = []

        # 事实锚点
        if context["fact_anchors"]:
            parts.append("【已知事实】")
            for fact in context["fact_anchors"][:3]:
                parts.append(f"- {fact['subject']} {fact['predicate']} {fact['object']}")
            parts.append("")

        # Few-Shot 示例
        if context["fewshot_examples"]:
            parts.append("【参考问答】")
            for i, ex in enumerate(context["fewshot_examples"], 1):
                parts.append(f"例{i}: 问：{ex['question']}")
                parts.append(f"   答：{ex['answer']}")
            parts.append("")

        # 相关实体
        if context["entities"]:
            parts.append("【相关实体】")
            for entity in context["entities"][:3]:
                parts.append(f"- {entity['name']}({entity['type']}): {entity['description']}")
            parts.append("")

        # 组装
        if parts:
            return "你已了解以下上下文信息：\n" + "\n".join(parts) + "\n\n" + original_prompt

        return original_prompt

    def update_quality_feedback(
        self,
        qa_id: str,
        is_helpful: bool
    ):
        """更新质量反馈"""
        delta = 0.1 if is_helpful else -0.1
        self.db.update_qa_quality(qa_id, delta)

    def get_preference(self, key: str, default: str = "") -> str:
        """获取用户偏好"""
        return self.db.get_preference(key, default)

    def set_preference(self, key: str, value: str, category: str = "general"):
        """设置用户偏好"""
        self.db.set_preference(key, value, category)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        db_stats = self.db.get_stats()
        return {
            **db_stats,
            "config": self.config
        }

    def export_knowledge(self, format: str = "json") -> str:
        """导出知识"""
        # 获取所有数据
        conn = sqlite3.connect(str(self.db.db_path))
        try:
            qa_rows = conn.execute("SELECT * FROM qa_pairs WHERE is_verified = 1").fetchall()
            entity_rows = conn.execute("SELECT * FROM entities").fetchall()
            fact_rows = conn.execute("SELECT * FROM facts WHERE value_level >= 2").fetchall()

            data = {
                "qa_pairs": [dict(zip([c[0] for c in conn.execute("SELECT * FROM qa_pairs LIMIT 0").description], r)) for r in qa_rows],
                "entities": [dict(zip([c[0] for c in conn.execute("SELECT * FROM entities LIMIT 0").description], r)) for r in entity_rows],
                "facts": [dict(zip([c[0] for c in conn.execute("SELECT * FROM facts LIMIT 0").description], r)) for r in fact_rows],
            }

            if format == "json":
                return json.dumps(data, ensure_ascii=False, indent=2)
            elif format == "markdown":
                # 转换为Markdown格式
                lines = ["# 知识库导出\n"]
                lines.append(f"\n## 问答对 ({len(data['qa_pairs'])})")
                for qa in data["qa_pairs"]:
                    lines.append(f"\n**Q: {qa['question']}**")
                    lines.append(f"A: {qa['answer']}")

                lines.append(f"\n## 实体 ({len(data['entities'])})")
                for e in data["entities"]:
                    lines.append(f"- {e['name']} ({e['entity_type']})")

                lines.append(f"\n## 事实 ({len(data['facts'])})")
                for f in data["facts"]:
                    lines.append(f"- {f['subject']} {f['predicate']} {f['object']}")

                return "\n".join(lines)

            return json.dumps(data)
        finally:
            conn.close()


# 单例
_memory_system: Optional[IntelligentMemorySystem] = None


def get_memory_system() -> IntelligentMemorySystem:
    """获取智能记忆系统单例"""
    global _memory_system
    if _memory_system is None:
        _memory_system = IntelligentMemorySystem()
    return _memory_system
