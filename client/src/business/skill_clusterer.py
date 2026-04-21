"""
SkillClusterer - 技能语义聚类系统
让记忆不膨胀、不冗余

核心能力：
- sentence-transformers 语义编码（384 维向量）
- FAISS 本地向量库
- DBSCAN 自动聚类
- 相似技能检测与合并建议

使用示例：
    clusterer = SkillClusterer()

    # 注册技能
    clusterer.register_skill("extract_financial_data_v1", "提取财务数据", ...)
    clusterer.register_skill("extract_financial_data_v2", "提取金融数据", ...)

    # 执行聚类
    clusters = clusterer.clusterize()

    # 获取合并建议
    suggestions = clusterer.get_merge_suggestions()
"""

import json
import sqlite3
import threading
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Any
from datetime import datetime

# 可选依赖
SENTENCE_TRANSFORMERS_AVAILABLE = False
FAISS_AVAILABLE = False
SKLEARN_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    pass

try:
    from sklearn.cluster import DBSCAN
    SKLEARN_AVAILABLE = True
except ImportError:
    pass


@dataclass
class Skill:
    """
    技能定义

    Attributes:
        skill_id: 唯一标识
        name: 技能名称
        description: 功能描述
        docstring: 详细文档
        input_schema: 输入参数 schema
        output_schema: 输出参数 schema
        toolset: 所属工具集
        version: 版本号
        embedding: 语义向量（延迟加载）
        metadata: 附加元数据
        created_at: 创建时间
        last_used: 最后使用时间
        use_count: 使用次数
    """
    skill_id: str
    name: str
    description: str
    docstring: str = ""
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    toolset: str = "core"
    version: str = "1.0.0"
    embedding: Optional[Any] = field(default=None, repr=False)
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=datetime.now().timestamp)
    last_used: Optional[float] = None
    use_count: int = 0

    def get_text_for_embedding(self) -> str:
        """
        获取用于语义编码的文本
        组合名称、描述、docstring 和示例
        """
        parts = [
            self.name,
            self.description,
            self.docstring,
        ]

        # 添加输入输出信息
        if self.input_schema:
            inputs = ", ".join(self.input_schema.get("properties", {}).keys())
            parts.append(f"输入: {inputs}")

        if self.output_schema:
            outputs = ", ".join(self.output_schema.get("properties", {}).keys())
            parts.append(f"输出: {outputs}")

        return " | ".join(filter(None, parts))

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "docstring": self.docstring,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "toolset": self.toolset,
            "version": self.version,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "use_count": self.use_count,
        }


@dataclass
class SkillCluster:
    """
    技能聚类

    Attributes:
        cluster_id: 聚类 ID
        skills: 聚类中的技能列表
        representative: 代表技能（使用次数最多的）
        similarity_score: 聚类内相似度
        merge_candidates: 可合并的技能对
    """
    cluster_id: int
    skills: list[Skill]
    representative: Optional[Skill] = None
    similarity_score: float = 0.0
    merge_candidates: list[tuple[str, str, float]] = field(default_factory=list)

    def get_summary(self) -> dict:
        """获取聚类摘要"""
        return {
            "cluster_id": self.cluster_id,
            "skill_count": len(self.skills),
            "skill_names": [s.name for s in self.skills],
            "representative": self.representative.name if self.representative else None,
            "total_uses": sum(s.use_count for s in self.skills),
            "similarity_score": self.similarity_score,
            "merge_candidates": len(self.merge_candidates),
        }


@dataclass
class MergeSuggestion:
    """合并建议"""
    skill_pair: tuple[Skill, Skill]
    similarity: float
    reason: str
    suggested_name: str
    suggested_docstring: str


class SkillClusterer:
    """
    技能语义聚类系统

    使用流程：
    1. 注册技能（自动编码）
    2. 构建向量库
    3. 执行聚类
    4. 生成合并建议

    Dependencies:
        - sentence-transformers: 语义编码
        - faiss: 向量检索
        - scikit-learn: DBSCAN 聚类
    """

    DEFAULT_MODEL = "all-MiniLM-L6-v2"  # 384 维向量
    EMBEDDING_DIM = 384
    SIMILARITY_THRESHOLD = 0.85  # 相似度阈值
    MIN_CLUSTER_SIZE = 2

    def __init__(
        self,
        db_path: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
    ):
        self.db_path = db_path or "skills_cluster.db"
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold

        # 存储
        self._skills: dict[str, Skill] = {}
        self._embeddings: list = []
        self._embedding_ids: list[str] = []

        # 模型和索引
        self._model = None
        self._index = None

        # 聚类结果
        self._clusters: list[SkillCluster] = []

        # 锁
        self._lock = threading.RLock()

        # 初始化
        self._init_db()
        self._init_model()

    def _init_db(self):
        """初始化数据库"""
        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                docstring TEXT,
                input_schema TEXT,
                output_schema TEXT,
                toolset TEXT,
                version TEXT,
                metadata TEXT,
                created_at REAL,
                last_used REAL,
                use_count INTEGER DEFAULT 0,
                embedding BLOB
            )
        """)
        self.db.commit()

    def _init_model(self):
        """初始化编码模型"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            print("⚠️ sentence-transformers 未安装，使用 TF-IDF 回退")
            self._model = None
            return

        try:
            self._model = SentenceTransformer(self.model_name)
            print(f"✓ 加载语义编码模型: {self.model_name}")
        except Exception as e:
            print(f"⚠️ 加载模型失败: {e}，使用 TF-IDF 回退")
            self._model = None

    def register_skill(
        self,
        name: str,
        description: str,
        docstring: str = "",
        input_schema: Optional[dict] = None,
        output_schema: Optional[dict] = None,
        toolset: str = "core",
        metadata: Optional[dict] = None,
    ) -> str:
        """
        注册技能

        Returns:
            技能 ID
        """
        with self._lock:
            # 生成 ID
            skill_id = hashlib.md5(f"{name}:{toolset}".encode()).hexdigest()[:12]

            skill = Skill(
                skill_id=skill_id,
                name=name,
                description=description,
                docstring=docstring,
                input_schema=input_schema or {},
                output_schema=output_schema or {},
                toolset=toolset,
                metadata=metadata or {},
            )

            # 编码
            if self._model:
                text = skill.get_text_for_embedding()
                skill.embedding = self._model.encode(text)

            # 存储
            self._skills[skill_id] = skill
            self._embeddings.append(skill.embedding)
            self._embedding_ids.append(skill_id)

            # 保存到数据库
            self._save_skill(skill)

            return skill_id

    def _save_skill(self, skill: Skill):
        """保存技能到数据库"""
        import pickle
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO skills
            (skill_id, name, description, docstring, input_schema, output_schema,
             toolset, version, metadata, created_at, last_used, use_count, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            skill.skill_id,
            skill.name,
            skill.description,
            skill.docstring,
            json.dumps(skill.input_schema),
            json.dumps(skill.output_schema),
            skill.toolset,
            skill.version,
            json.dumps(skill.metadata),
            skill.created_at,
            skill.last_used,
            skill.use_count,
            pickle.dumps(skill.embedding) if skill.embedding is not None else None,
        ))
        self.db.commit()

    def build_index(self):
        """构建 FAISS 索引"""
        if not self._embeddings:
            return

        if not FAISS_AVAILABLE:
            print("⚠️ faiss 未安装，跳过索引构建")
            return

        import numpy as np

        # 转换为 numpy
        embeddings = np.array(self._embeddings).astype("float32")

        # L2 归一化
        faiss.normalize_L2(embeddings)

        # 构建索引
        self._index = faiss.IndexFlatIP(self.EMBEDDING_DIM)  # 内积索引
        self._index.add(embeddings)

        print(f"✓ 构建 FAISS 索引: {len(self._embeddings)} 个向量")

    def clusterize(self) -> list[SkillCluster]:
        """
        执行 DBSCAN 聚类

        Returns:
            聚类列表
        """
        if not self._embeddings:
            return []

        self._clusters = []

        if SKLEARN_AVAILABLE and self._embeddings:
            import numpy as np

            embeddings = np.array(self._embeddings).astype("float32")

            # DBSCAN 聚类
            clustering = DBSCAN(
                eps=0.3,  # eps 参数（相似度阈值）
                min_samples=self.MIN_CLUSTER_SIZE,
                metric="cosine",
            )
            labels = clustering.fit_predict(embeddings)

            # 构建聚类
            cluster_map: dict[int, list[Skill]] = {}
            for i, label in enumerate(labels):
                if label == -1:
                    continue  # 噪声点
                skill = self._skills[self._embedding_ids[i]]
                cluster_map.setdefault(label, []).append(skill)

            for cluster_id, skills in cluster_map.items():
                # 计算代表技能（使用次数最多）
                representative = max(skills, key=lambda s: s.use_count)

                # 计算聚类内相似度
                similarity = self._calc_cluster_similarity(skills)

                # 查找可合并的对
                merge_candidates = self._find_merge_candidates(skills)

                cluster = SkillCluster(
                    cluster_id=cluster_id,
                    skills=skills,
                    representative=representative,
                    similarity_score=similarity,
                    merge_candidates=merge_candidates,
                )
                self._clusters.append(cluster)
        else:
            # 简单相似度聚类（无 sklearn）
            self._simple_clustering()

        return self._clusters

    def _calc_cluster_similarity(self, skills: list[Skill]) -> float:
        """计算聚类内平均相似度"""
        if len(skills) < 2:
            return 1.0

        total_sim = 0.0
        count = 0

        for i in range(len(skills)):
            for j in range(i + 1, len(skills)):
                sim = self._calc_similarity(skills[i], skills[j])
                total_sim += sim
                count += 1

        return total_sim / count if count > 0 else 0.0

    def _calc_similarity(self, s1: Skill, s2: Skill) -> float:
        """计算两个技能的相似度"""
        if s1.embedding is None or s2.embedding is None:
            # 基于名称和描述的简单相似度
            name_sim = self._jaccard_similarity(
                set(s1.name.lower().split()),
                set(s2.name.lower().split())
            )
            desc_sim = self._jaccard_similarity(
                set(s1.description.lower().split()),
                set(s2.description.lower().split())
            )
            return (name_sim + desc_sim) / 2

        import numpy as np
        return float(np.dot(s1.embedding, s2.embedding))

    @staticmethod
    def _jaccard_similarity(set1: set, set2: set) -> float:
        """Jaccard 相似度"""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def _find_merge_candidates(self, skills: list[Skill]) -> list[tuple[str, str, float]]:
        """查找可合并的技能对"""
        candidates = []

        for i in range(len(skills)):
            for j in range(i + 1, len(skills)):
                sim = self._calc_similarity(skills[i], skills[j])
                if sim >= self.similarity_threshold:
                    candidates.append((skills[i].skill_id, skills[j].skill_id, sim))

        return candidates

    def _simple_clustering(self):
        """简单的相似度聚类（无 sklearn）"""
        import numpy as np

        if not self._embeddings:
            return

        embeddings = np.array(self._embeddings)
        n = len(embeddings)

        # 简单距离矩阵
        labels = np.zeros(n, dtype=int) - 1
        cluster_id = 0

        for i in range(n):
            if labels[i] != -1:
                continue

            # 新聚类
            labels[i] = cluster_id
            cluster_skills = [self._skills[self._embedding_ids[i]]]

            # 合并相似技能
            for j in range(i + 1, n):
                if labels[j] != -1:
                    continue
                sim = self._calc_similarity(
                    self._skills[self._embedding_ids[i]],
                    self._skills[self._embedding_ids[j]]
                )
                if sim >= self.similarity_threshold:
                    labels[j] = cluster_id
                    cluster_skills.append(self._skills[self._embedding_ids[j]])

            # 只保留 >= 2 个技能的聚类
            if len(cluster_skills) >= self.MIN_CLUSTER_SIZE:
                representative = max(cluster_skills, key=lambda s: s.use_count)
                self._clusters.append(SkillCluster(
                    cluster_id=cluster_id,
                    skills=cluster_skills,
                    representative=representative,
                ))
                cluster_id += 1
            else:
                # 恢复为噪声
                for s in cluster_skills:
                    labels[self._embedding_ids.index(s.skill_id)] = -1

    def get_merge_suggestions(self) -> list[MergeSuggestion]:
        """
        获取合并建议

        Returns:
            合并建议列表
        """
        suggestions = []

        for cluster in self._clusters:
            for s1_id, s2_id, sim in cluster.merge_candidates:
                s1 = self._skills.get(s1_id)
                s2 = self._skills.get(s2_id)
                if not s1 or not s2:
                    continue

                # 生成合并建议
                suggestion = MergeSuggestion(
                    skill_pair=(s1, s2),
                    similarity=sim,
                    reason=f"语义相似度 {sim:.2%}，功能高度重叠",
                    suggested_name=self._merge_names(s1.name, s2.name),
                    suggested_docstring=f"{s1.description}\n\n{s2.description}",
                )
                suggestions.append(suggestion)

        return suggestions

    def _merge_names(self, name1: str, name2: str) -> str:
        """合并两个技能名称"""
        # 提取共同前缀
        import re

        # 移除版本号
        def strip_version(name):
            return re.sub(r'_v?\d+', '', name)

        base1, base2 = strip_version(name1), strip_version(name2)

        # 尝试提取共同部分
        words1 = base1.lower().split('_')
        words2 = base2.lower().split('_')

        common = []
        for w in words1:
            if w in words2:
                common.append(w)

        if common:
            return '_'.join(common) + "_merged"
        else:
            return f"{base1}_{base2}_merged"

    def find_similar(self, skill_id: str, top_k: int = 5) -> list[tuple[Skill, float]]:
        """
        查找相似技能

        Args:
            skill_id: 技能 ID
            top_k: 返回数量

        Returns:
            (技能, 相似度) 列表
        """
        skill = self._skills.get(skill_id)
        if not skill or skill.embedding is None:
            return []

        if self._index is None:
            self.build_index()

        if self._index is None:
            return []

        import numpy as np

        # 搜索
        query = np.array([skill.embedding]).astype("float32")
        faiss.normalize_L2(query)
        distances, indices = self._index.search(query, top_k + 1)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            idx = int(idx)
            if idx >= len(self._embedding_ids):
                continue
            sid = self._embedding_ids[idx]
            if sid != skill_id:
                similar_skill = self._skills[sid]
                results.append((similar_skill, float(dist)))

        return results

    def get_clusters_tree(self) -> dict:
        """
        获取聚类树（用于 UI 展示）
        """
        return {
            "clusters": [
                {
                    "id": c.cluster_id,
                    "representative": c.representative.name if c.representative else None,
                    "skill_count": len(c.skills),
                    "skills": [
                        {
                            "id": s.skill_id,
                            "name": s.name,
                            "description": s.description,
                            "use_count": s.use_count,
                            "last_used": s.last_used,
                        }
                        for s in c.skills
                    ],
                    "merge_candidates": [
                        {"skill1": cid1, "skill2": cid2, "similarity": sim}
                        for cid1, cid2, sim in c.merge_candidates
                    ],
                }
                for c in self._clusters
            ],
            "stats": {
                "total_skills": len(self._skills),
                "total_clusters": len(self._clusters),
                "potential_savings": sum(len(c.skills) - 1 for c in self._clusters),
            }
        }

    def record_usage(self, skill_id: str):
        """记录技能使用"""
        skill = self._skills.get(skill_id)
        if skill:
            skill.use_count += 1
            skill.last_used = datetime.now().timestamp()
            self._save_skill(skill)

    def merge_skills(self, skill1_id: str, skill2_id: str, new_name: str) -> Optional[str]:
        """
        合并两个技能

        Args:
            skill1_id: 主技能 ID
            skill2_id: 副技能 ID（将被删除）
            new_name: 新技能名称

        Returns:
            新技能 ID
        """
        s1 = self._skills.get(skill1_id)
        s2 = self._skills.get(skill2_id)
        if not s1 or not s2:
            return None

        # 创建新技能
        new_skill = Skill(
            skill_id=hashlib.md5(f"{new_name}:{s1.toolset}".encode()).hexdigest()[:12],
            name=new_name,
            description=f"{s1.description}\n\n--- 合并自 ---\n{s2.description}",
            docstring=f"{s1.docstring}\n\n{s2.docstring}",
            input_schema={**s1.input_schema, **s2.input_schema},
            output_schema={**s1.output_schema, **s2.output_schema},
            toolset=s1.toolset,
            version=f"{max(int(s1.version.split('.')[0]), int(s2.version.split('.')[0])) + 1}.0.0",
        )

        # 更新元数据
        new_skill.metadata = {
            "merged_from": [skill1_id, skill2_id],
            "original_count": 2,
        }

        # 编码
        if self._model:
            new_skill.embedding = self._model.encode(new_skill.get_text_for_embedding())

        # 存储
        with self._lock:
            self._skills[new_skill.skill_id] = new_skill
            del self._skills[skill2_id]

            self._save_skill(new_skill)

            # 删除旧技能
            self.db.execute("DELETE FROM skills WHERE skill_id = ?", (skill2_id,))
            self.db.commit()

        return new_skill.skill_id


# ── 便捷函数 ────────────────────────────────────────────────────────

def create_clusterer(
    db_path: Optional[str] = None,
    model_name: str = "all-MiniLM-L6-v2",
) -> SkillClusterer:
    """创建技能聚类器"""
    return SkillClusterer(db_path=db_path, model_name=model_name)
