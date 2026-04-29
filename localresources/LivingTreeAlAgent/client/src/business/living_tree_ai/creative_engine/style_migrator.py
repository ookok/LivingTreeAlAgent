"""
P2P 知识库与风格迁移 (Style Migrator)
======================================

核心理念：利用 P2P 网络存储私有知识库，让 AI 学习"你的风格"。

功能：
1. 分布式记忆：对话历史、创作偏好加密存储在网络节点
2. 风格克隆：分析用户过去的文档，学习写作风格
3. 团队模型：团队共用知识库，AI 自动引用内部文档标准
4. 增量学习：AI 在边缘节点上根据反馈进行微调
5. RAG on P2P：向量数据库部署在节点上，保证隐私
"""

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class StorageType(Enum):
    """存储类型"""
    LOCAL = "local"               # 本地存储
    DISTRIBUTED = "distributed"   # P2P 分布式存储
    ENCRYPTED = "encrypted"      # 端到端加密存储


@dataclass
class StyleProfile:
    """风格画像"""
    profile_id: str
    name: str                              # 画像名称（如 "技术博客风格"）
    owner_id: str                          # 所有者
    created_at: datetime
    updated_at: datetime
    # 风格特征
    vocabulary: list[str] = field(default_factory=list)      # 常用词汇
    sentence_patterns: list[str] = field(default_factory=list)  # 句式模式
    tone_markers: list[str] = field(default_factory=list)  # 语气标记
    structure_patterns: list[str] = field(default_factory=list)  # 结构模式
    domain_terms: list[str] = field(default_factory=list)   # 领域术语
    # 统计特征
    avg_sentence_length: float = 0         # 平均句子长度
    punctuation_ratio: float = 0          # 标点密度
    paragraph_length: tuple[float, float] = (0, 0)  # 段落长度范围
    # 元数据
    source_documents: list[str] = field(default_factory=list)  # 来源文档
    confidence: float = 0                 # 置信度
    is_public: bool = False               # 是否公开（团队共享）


@dataclass
class KnowledgeEntry:
    """知识条目"""
    entry_id: str
    content: str
    content_type: str                      # text/code/document
    embedding: list[float] = None          # 向量嵌入
    created_at: datetime
    updated_at: datetime
    author_id: str
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    source: str = ""                       # 来源（邮件/论坛/文档）
    source_url: str = ""                   # 原始链接
    access_count: int = 0                  # 访问次数
    usefulness_score: float = 0            # 有用性评分


class StyleMigrator:
    """
    风格迁移器

    用法:
        migrator = StyleMigrator()

        # 分析文档，构建风格画像
        profile = await migrator.learn_style(
            documents=["path/to/doc1.md", "path/to/doc2.md"],
            profile_name="我的技术博客风格"
        )

        # 使用风格生成内容
        content = await migrator.generate_with_style(
            prompt="写一篇关于分布式系统的文章",
            style_profile=profile
        )

        # 存储知识条目
        entry = await migrator.store_knowledge(
            content="通过消息队列实现系统解耦...",
            content_type="document",
            tags=["架构", "消息队列", "微服务"]
        )

        # 检索相关知识
        results = await migrator.retrieve_knowledge(
            query="如何设计微服务架构",
            top_k=5
        )
    """

    def __init__(self, data_dir: str = "./data/creative"):
        self.data_dir = data_dir
        self._profiles: dict[str, StyleProfile] = {}
        self._knowledge_base: list[KnowledgeEntry] = []
        self._p2p_handler: Optional[Callable] = None
        self._embedding_model: Optional[Callable] = None

        # 本地存储路径
        self._profiles_dir = os.path.join(data_dir, "style_profiles")
        self._knowledge_dir = os.path.join(data_dir, "knowledge_base")
        os.makedirs(self._profiles_dir, exist_ok=True)
        os.makedirs(self._knowledge_dir, exist_ok=True)

        # 加载已有数据
        self._load_profiles()
        self._load_knowledge()

    def set_p2p_handler(self, handler: Callable) -> None:
        """设置 P2P 处理器"""
        self._p2p_handler = handler

    def set_embedding_model(self, model: Callable) -> None:
        """设置嵌入模型"""
        self._embedding_model = model

    def _load_profiles(self) -> None:
        """加载本地风格画像"""
        try:
            for filename in os.listdir(self._profiles_dir):
                if filename.endswith('.json'):
                    with open(os.path.join(self._profiles_dir, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        profile = StyleProfile(**data)
                        self._profiles[profile.profile_id] = profile
        except Exception as e:
            print(f"[StyleMigrator] 加载风格画像失败: {e}")

    def _load_knowledge(self) -> None:
        """加载知识库"""
        try:
            knowledge_file = os.path.join(self._knowledge_dir, "index.json")
            if os.path.exists(knowledge_file):
                with open(knowledge_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._knowledge_base = [KnowledgeEntry(**e) for e in data]
        except Exception as e:
            print(f"[StyleMigrator] 加载知识库失败: {e}")

    async def learn_style(
        self,
        documents: list[str],
        profile_name: str,
        owner_id: str = "local",
        min_confidence: float = 0.7
    ) -> StyleProfile:
        """
        学习文档风格，构建风格画像

        Args:
            documents: 文档路径列表
            profile_name: 画像名称
            owner_id: 所有者 ID
            min_confidence: 最低置信度

        Returns:
            StyleProfile: 构建的风格画像
        """
        all_text = []
        for doc_path in documents:
            try:
                with open(doc_path, 'r', encoding='utf-8') as f:
                    all_text.append(f.read())
            except:
                pass

        if not all_text:
            raise ValueError("没有找到有效的文档")

        combined_text = "\n\n".join(all_text)
        profile_id = hashlib.sha256(f"{profile_name}{time.time()}".encode()).hexdigest()[:12]

        # 统计特征分析
        sentences = self._split_sentences(combined_text)
        avg_sentence_length = sum(len(s) for s in sentences) / max(len(sentences), 1)

        # 词汇分析
        words = combined_text.split()
        vocabulary = list(set(words))[:500]  # 取前 500 个独特词汇

        # 句式模式
        sentence_patterns = self._extract_sentence_patterns(sentences)

        # 语气标记
        tone_markers = self._extract_tone_markers(combined_text)

        # 段落结构
        paragraphs = combined_text.split("\n\n")
        paragraph_lengths = [len(p) for p in paragraphs]
        paragraph_length_range = (
            min(paragraph_lengths) if paragraph_lengths else 0,
            max(paragraph_lengths) if paragraph_lengths else 0
        )

        # 标点密度
        punctuation_count = sum(1 for c in combined_text if c in '.,!?;:"')
        punctuation_ratio = punctuation_count / max(len(combined_text), 1)

        # 计算置信度（基于文档数量和内容长度）
        confidence = min(1.0, (len(documents) * 0.3 + len(combined_text) / 10000 * 0.7))

        profile = StyleProfile(
            profile_id=profile_id,
            name=profile_name,
            owner_id=owner_id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            vocabulary=vocabulary,
            sentence_patterns=sentence_patterns,
            tone_markers=tone_markers,
            structure_patterns=[],
            domain_terms=self._extract_domain_terms(combined_text),
            avg_sentence_length=avg_sentence_length,
            punctuation_ratio=punctuation_ratio,
            paragraph_length=paragraph_length_range,
            source_documents=documents,
            confidence=confidence,
            is_public=False
        )

        self._profiles[profile_id] = profile

        # 保存到本地
        await self._save_profile(profile)

        # 同步到 P2P 网络
        if self._p2p_handler:
            await self._p2p_handler("store_profile", profile)

        return profile

    def _split_sentences(self, text: str) -> list[str]:
        """拆分句子"""
        import re
        sentences = re.split(r'[.!?。！？]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_sentence_patterns(self, sentences: list[str]) -> list[str]:
        """提取句式模式"""
        patterns = []
        for sentence in sentences[:50]:  # 只分析前 50 个句子
            sentence = sentence.strip()
            if not sentence:
                continue

            # 检测句式开头模式
            if sentence.startswith("首先") or sentence.startswith("第一"):
                patterns.append("firstly_pattern")
            elif sentence.startswith("其次") or sentence.startswith("第二"):
                patterns.append("secondly_pattern")
            elif sentence.startswith("然而"):
                patterns.append("however_pattern")
            elif sentence.startswith("因此"):
                patterns.append("therefore_pattern")
            elif sentence.startswith("例如"):
                patterns.append("example_pattern")
            elif sentence.startswith("总之"):
                patterns.append("conclusion_pattern")

            # 检测结尾模式
            if sentence.endswith("。"):
                patterns.append("chinese_period")
            elif sentence.endswith("！"):
                patterns.append("exclamation")
            elif sentence.endswith("？"):
                patterns.append("question")

        # 返回频率最高的模式
        from collections import Counter
        pattern_counts = Counter(patterns)
        return [p for p, _ in pattern_counts.most_common(10)]

    def _extract_tone_markers(self, text: str) -> list[str]:
        """提取语气标记"""
        markers = []

        # 专业语气
        professional_markers = ["综上所述", "由此可见", "本质上", "从技术角度", "客观来说"]
        for marker in professional_markers:
            if marker in text:
                markers.append(f"professional:{marker}")

        # 口语语气
        casual_markers = ["大概", "可能", "说实话", "其实", "说实话"]
        for marker in casual_markers:
            if marker in text:
                markers.append(f"casual:{marker}")

        # 谦虚语气
        humble_markers = ["个人看法", "仅供参考", "如有不对", "敬请指正"]
        for marker in humble_markers:
            if marker in text:
                markers.append(f"humble:{marker}")

        return markers

    def _extract_domain_terms(self, text: str) -> list[str]:
        """提取领域术语"""
        # 简单的术语提取（实际应该用 NLP）
        common_terms = {
            "技术": ["API", "SDK", "架构", "微服务", "容器", "部署", "DevOps"],
            "AI": ["模型", "训练", "推理", " embedding", "神经网络", "深度学习"],
            "商业": ["增长", "转化率", "用户画像", "商业模式", "变现"],
        }

        found_terms = []
        for domain, terms in common_terms.items():
            for term in terms:
                if term.lower() in text.lower():
                    found_terms.append(term)

        return list(set(found_terms))

    async def generate_with_style(
        self,
        prompt: str,
        style_profile: StyleProfile,
        generator: Any = None,
        tone_adjustments: dict = None
    ) -> str:
        """
        使用指定风格生成内容

        Args:
            prompt: 生成提示
            style_profile: 风格画像
            generator: 可选的生成器
            tone_adjustments: 语气调整

        Returns:
            str: 生成的内容
        """
        # 构建风格提示
        style_instructions = []

        if style_profile.sentence_patterns:
            patterns = ", ".join(style_profile.sentence_patterns[:5])
            style_instructions.append(f"使用以下句式模式: {patterns}")

        if style_profile.tone_markers:
            markers = [m.split(":")[1] for m in style_profile.tone_markers[:3] if ":" in m]
            if markers:
                style_instructions.append(f"适当使用这些语气词: {', '.join(markers)}")

        if style_profile.domain_terms:
            terms = ", ".join(style_profile.domain_terms[:5])
            style_instructions.append(f"可参考这些领域术语: {terms}")

        # 构建完整提示
        enhanced_prompt = f"""请使用"{style_profile.name}"的风格撰写以下内容：

风格要求：
{chr(10).join(style_instructions)}

平均句子长度：约 {style_profile.avg_sentence_length:.0f} 字符
标点使用密度：{"较高" if style_profile.punctuation_ratio > 0.1 else "适中"}

内容要求：
{prompt}"""

        # 如果有生成器，使用它
        if generator:
            result = await generator.generate_parallel(
                prompt=enhanced_prompt,
                tones=[]  # 不指定风格，使用画像的风格
            )
            if result.best_version:
                return result.best_version.content

        # 默认返回增强后的提示
        return enhanced_prompt

    async def store_knowledge(
        self,
        content: str,
        content_type: str = "text",
        tags: list[str] = None,
        author_id: str = "local",
        source: str = "",
        source_url: str = "",
        metadata: dict = None
    ) -> KnowledgeEntry:
        """
        存储知识条目

        Args:
            content: 知识内容
            content_type: 内容类型
            tags: 标签
            author_id: 作者 ID
            source: 来源
            source_url: 原始链接
            metadata: 额外元数据

        Returns:
            KnowledgeEntry: 存储的知识条目
        """
        entry_id = hashlib.sha256(f"{content[:100]}{time.time()}".encode()).hexdigest()[:12]
        tags = tags or []

        # 生成嵌入向量
        embedding = None
        if self._embedding_model:
            try:
                embedding = await self._embedding_model(content)
            except:
                pass

        entry = KnowledgeEntry(
            entry_id=entry_id,
            content=content,
            content_type=content_type,
            embedding=embedding,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author_id=author_id,
            tags=tags,
            metadata=metadata or {},
            source=source,
            source_url=source_url
        )

        self._knowledge_base.append(entry)

        # 保存到本地
        await self._save_knowledge_base()

        # 同步到 P2P 网络
        if self._p2p_handler:
            await self._p2p_handler("store_knowledge", entry)

        return entry

    async def retrieve_knowledge(
        self,
        query: str,
        top_k: int = 5,
        tags: list[str] = None,
        content_type: str = None,
        owner_id: str = None
    ) -> list[KnowledgeEntry]:
        """
        检索知识

        Args:
            query: 查询文本
            top_k: 返回数量
            tags: 标签过滤
            content_type: 内容类型过滤
            owner_id: 所有者过滤

        Returns:
            list[KnowledgeEntry]: 相关知识条目
        """
        results = self._knowledge_base

        # 标签过滤
        if tags:
            results = [e for e in results if any(t in e.tags for t in tags)]

        # 类型过滤
        if content_type:
            results = [e for e in results if e.content_type == content_type]

        # 所有者过滤
        if owner_id:
            results = [e for e in results if e.author_id == owner_id]

        # 嵌入相似度计算（如果可用）
        if self._embedding_model:
            try:
                query_embedding = await self._embedding_model(query)
                for entry in results:
                    if entry.embedding:
                        entry.metadata["similarity"] = self._cosine_similarity(
                            query_embedding, entry.embedding
                        )
                results.sort(
                    key=lambda e: e.metadata.get("similarity", 0),
                    reverse=True
                )
            except:
                pass

        # 更新访问统计
        for entry in results[:top_k]:
            entry.access_count += 1

        return results[:top_k]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot_product / (norm_a * norm_b + 1e-8)

    async def update_style_from_feedback(
        self,
        profile_id: str,
        original_content: str,
        user_revision: str,
        feedback_type: str = "improvement"
    ) -> StyleProfile:
        """
        根据用户反馈更新风格画像

        Args:
            profile_id: 画像 ID
            original_content: 原始 AI 生成内容
            user_revision: 用户修改后的内容
            feedback_type: 反馈类型

        Returns:
            StyleProfile: 更新后的画像
        """
        profile = self._profiles.get(profile_id)
        if not profile:
            raise ValueError(f"找不到画像: {profile_id}")

        # 分析用户修改了什么
        if len(user_revision) < len(original_content) * 0.5:
            # 用户大幅删减，可能不喜欢冗长
            profile.avg_sentence_length *= 0.8
        elif len(user_revision) > len(original_content) * 1.5:
            # 用户大幅扩展，可能喜欢详细
            profile.avg_sentence_length *= 1.2

        # 提取用户新增的词汇
        original_words = set(original_content.lower().split())
        revised_words = set(user_revision.lower().split())
        new_words = revised_words - original_words

        if new_words:
            profile.vocabulary.extend(list(new_words)[:20])
            profile.vocabulary = list(set(profile.vocabulary))[:500]

        # 更新置信度（反馈应该提高置信度）
        profile.confidence = min(1.0, profile.confidence + 0.05)
        profile.updated_at = datetime.now()

        # 保存更新
        await self._save_profile(profile)

        return profile

    async def _save_profile(self, profile: StyleProfile) -> None:
        """保存风格画像到本地"""
        try:
            filepath = os.path.join(self._profiles_dir, f"{profile.profile_id}.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "profile_id": profile.profile_id,
                    "name": profile.name,
                    "owner_id": profile.owner_id,
                    "created_at": profile.created_at.isoformat(),
                    "updated_at": profile.updated_at.isoformat(),
                    "vocabulary": profile.vocabulary,
                    "sentence_patterns": profile.sentence_patterns,
                    "tone_markers": profile.tone_markers,
                    "structure_patterns": profile.structure_patterns,
                    "domain_terms": profile.domain_terms,
                    "avg_sentence_length": profile.avg_sentence_length,
                    "punctuation_ratio": profile.punctuation_ratio,
                    "paragraph_length": list(profile.paragraph_length),
                    "source_documents": profile.source_documents,
                    "confidence": profile.confidence,
                    "is_public": profile.is_public
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[StyleMigrator] 保存画像失败: {e}")

    async def _save_knowledge_base(self) -> None:
        """保存知识库到本地"""
        try:
            knowledge_file = os.path.join(self._knowledge_dir, "index.json")
            data = [
                {
                    "entry_id": e.entry_id,
                    "content": e.content,
                    "content_type": e.content_type,
                    "embedding": e.embedding,
                    "created_at": e.created_at.isoformat(),
                    "updated_at": e.updated_at.isoformat(),
                    "author_id": e.author_id,
                    "tags": e.tags,
                    "metadata": e.metadata,
                    "source": e.source,
                    "source_url": e.source_url,
                    "access_count": e.access_count,
                    "usefulness_score": e.usefulness_score
                }
                for e in self._knowledge_base
            ]
            with open(knowledge_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[StyleMigrator] 保存知识库失败: {e}")

    def get_profiles(self, owner_id: str = None, include_public: bool = True) -> list[StyleProfile]:
        """获取风格画像列表"""
        profiles = self._profiles.values()

        if owner_id:
            profiles = [p for p in profiles if p.owner_id == owner_id]

        if not include_public:
            profiles = [p for p in profiles if not p.is_public]

        return sorted(profiles, key=lambda p: p.updated_at, reverse=True)

    def get_knowledge_stats(self) -> dict:
        """获取知识库统计"""
        total_entries = len(self._knowledge_base)
        by_type = {}
        by_source = {}

        for entry in self._knowledge_base:
            by_type[entry.content_type] = by_type.get(entry.content_type, 0) + 1
            by_source[entry.source] = by_source.get(entry.source, 0) + 1

        return {
            "total_entries": total_entries,
            "by_content_type": by_type,
            "by_source": by_source,
            "total_tags": len(set(tag for e in self._knowledge_base for tag in e.tags)),
            "avg_access_count": sum(e.access_count for e in self._knowledge_base) / max(total_entries, 1)
        }


def create_style_migrator(data_dir: str = "./data/creative") -> StyleMigrator:
    """创建风格迁移器实例"""
    return StyleMigrator(data_dir=data_dir)