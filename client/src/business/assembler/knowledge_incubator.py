"""
🌱 知识孵化器 (Knowledge Incubator)
===================================

装配园扩展：从"安装工具"到"孕育知识"

三阶知识孵化管线：
1. 🌾 沃土播种 (Soil Sowing) - 知识库生成
2. 🛠️ 技能嫁接 (Skill Grafting) - Skill生成
3. 🔄 园丁整理架 (Gardener's Shelf) - 自动整理

输入（文字/博客/代码） → 解析提炼 → 知识库条目 + Skill → 存入沃土库 → 生命之树可检索/调用
"""

import json
import re
import hashlib
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable, Any, List
from datetime import datetime
from enum import Enum

import yaml


# ==================== 知识条目数据模型 ====================

class KnowledgeType(Enum):
    """知识类型"""
    ARTICLE = "article"           # 文章/博客
    DOCUMENTATION = "doc"         # 文档
    API_REFERENCE = "api"         # API参考
    CODE_SNIPPET = "code"         # 代码片段
    TUTORIAL = "tutorial"         # 教程
    BEST_PRACTICE = "best_practice"  # 最佳实践
    QNA = "qna"                  # 问答


@dataclass
class KnowledgeEntry:
    """
    知识条目

    存储在 soil_bank/knowledge/{category}/{id}.json
    """
    id: str                          # 唯一标识 (know_{hash8}_{date})
    title: str                       # 标题
    content_md: str                   # Markdown内容
    summary: str                      # 摘要（AI生成）
    source_url: str = ""              # 来源URL
    source_type: str = "unknown"      # 来源类型
    knowledge_type: str = "article"   # 知识类型
    tags: List[str] = field(default_factory=list)  # 标签
    language: str = ""                # 编程语言（如适用）
    difficulty: str = "intermediate"  # 难度
    created_at: str = ""              # 创建时间
    updated_at: str = ""              # 更新时间
    usage_count: int = 0             # 调用次数
    embedding: str = ""               # 向量嵌入（未来扩展）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'KnowledgeEntry':
        return cls(**data)

    def to_markdown(self) -> str:
        """导出为Markdown"""
        lines = [
            f"# {self.title}",
            "",
            f"**ID**: `{self.id}`",
            f"**类型**: {self.knowledge_type}",
            f"**标签**: {', '.join(self.tags)}",
            f"**来源**: {self.source_url or 'N/A'}",
            f"**创建**: {self.created_at}",
            "",
            "---",
            "",
            "## 摘要",
            self.summary,
            "",
            "---",
            "",
            "## 正文",
            self.content_md,
        ]
        return "\n".join(lines)


# ==================== Skill生成数据模型 ====================

@dataclass
class GeneratedSkill:
    """
    生成的Skill

    存储在 skills/generated/{name}/
    """
    name: str                         # Skill名称
    description: str                  # 描述
    version: str = "1.0.0"            # 版本
    category: str = "custom"          # 分类
    language: str = ""                # 编程语言
    source_repo: str = ""             # 来源仓库

    # YAML配置
    triggers: List[str] = field(default_factory=list)  # 触发词
    capabilities: List[str] = field(default_factory=list)  # 能力列表
    dependencies: List[str] = field(default_factory=list)  # 依赖
    parameters: dict = field(default_factory=dict)  # 参数定义

    # 生成的文件
    manifest_content: str = ""        # SKILL.md内容
    adapter_content: str = ""         # 适配器代码
    examples: List[str] = field(default_factory=list)  # 示例

    created_at: str = ""

    def to_skill_manifest(self) -> str:
        """生成SKILL.md"""
        manifest = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "triggers": self.triggers,
            "capabilities": self.capabilities,
            "dependencies": self.dependencies,
            "parameters": self.parameters,
            "examples": self.examples,
            "author": "Hermes Knowledge Incubator",
            "generated_at": self.created_at,
            "source_repo": self.source_repo,
        }
        return "---\n" + yaml.dump(manifest, allow_unicode=True, sort_keys=False)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "language": self.language,
            "source_repo": self.source_repo,
            "triggers": self.triggers,
            "capabilities": self.capabilities,
            "dependencies": self.dependencies,
            "parameters": self.parameters,
            "examples": self.examples,
            "created_at": self.created_at,
        }


# ==================== 知识库管理器 ====================

class KnowledgeBank:
    """
    知识库管理器

    负责知识的存储、检索、去重
    """

    def __init__(self, base_path: str | Path = None):
        if base_path is None:
            base_path = Path.home() / ".hermes-desktop" / "soil_bank"
        self.base_path = Path(base_path)
        self.knowledge_dir = self.base_path / "knowledge"
        self.skills_dir = self.base_path / "skills"
        self.db_path = self.base_path / "knowledge_bank.db"

        # 创建目录
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT,
                source_url TEXT,
                source_type TEXT,
                knowledge_type TEXT,
                tags TEXT,
                language TEXT,
                difficulty TEXT,
                created_at TEXT,
                updated_at TEXT,
                usage_count INTEGER DEFAULT 0,
                content_hash TEXT UNIQUE,
                file_path TEXT
            );

            CREATE TABLE IF NOT EXISTS generated_skills (
                name TEXT PRIMARY KEY,
                description TEXT,
                version TEXT,
                category TEXT,
                language TEXT,
                source_repo TEXT,
                manifest_content TEXT,
                adapter_content TEXT,
                created_at TEXT,
                file_path TEXT
            );

            CREATE TABLE IF NOT EXISTS tag_index (
                tag TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_knowledge_tags ON knowledge_entries(tags);
            CREATE INDEX IF NOT EXISTS idx_knowledge_type ON knowledge_entries(knowledge_type);
            CREATE INDEX IF NOT EXISTS idx_knowledge_source ON knowledge_entries(source_url);
        """)
        conn.commit()
        conn.close()

    def _generate_id(self, title: str, source_url: str = "") -> str:
        """生成唯一ID"""
        date = datetime.now().strftime("%Y%m%d")
        content = f"{title}:{source_url}:{date}"
        hash8 = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"know_{hash8}_{date}"

    def _content_hash(self, content: str) -> str:
        """计算内容hash"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def save_knowledge(self, entry: KnowledgeEntry) -> tuple[bool, str]:
        """
        保存知识条目

        Returns:
            (success, message)
        """
        # 生成ID
        if not entry.id:
            entry.id = self._generate_id(entry.title, entry.source_url)

        # 设置时间
        now = datetime.now().isoformat()
        if not entry.created_at:
            entry.created_at = now
        entry.updated_at = now

        # 内容hash（用于去重）
        content_hash = self._content_hash(entry.content_md)

        conn = sqlite3.connect(str(self.db_path))
        try:
            # 检查是否重复
            cursor = conn.execute(
                "SELECT id FROM knowledge_entries WHERE content_hash = ?",
                (content_hash,)
            )
            existing = cursor.fetchone()
            if existing:
                return False, f"知识条目已存在: {existing[0]}"

            # 确定分类目录
            category = entry.tags[0] if entry.tags else "general"
            category_dir = self.knowledge_dir / category
            category_dir.mkdir(exist_ok=True)

            # 保存文件
            file_path = category_dir / f"{entry.id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2)

            # 保存到数据库
            conn.execute("""
                INSERT INTO knowledge_entries
                (id, title, summary, source_url, source_type, knowledge_type,
                 tags, language, difficulty, created_at, updated_at, content_hash, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id, entry.title, entry.summary, entry.source_url,
                entry.source_type, entry.knowledge_type,
                ",".join(entry.tags), entry.language, entry.difficulty,
                entry.created_at, entry.updated_at, content_hash, str(file_path)
            ))

            # 更新标签索引
            for tag in entry.tags:
                conn.execute("""
                    INSERT INTO tag_index (tag, count) VALUES (?, 1)
                    ON CONFLICT(tag) DO UPDATE SET count = count + 1
                """, (tag,))

            conn.commit()
            return True, f"知识条目已保存: {entry.id}"

        except Exception as e:
            conn.rollback()
            return False, f"保存失败: {e}"
        finally:
            conn.close()

    def save_skill(self, skill: GeneratedSkill) -> tuple[bool, str]:
        """
        保存生成的Skill

        Returns:
            (success, message)
        """
        skill_dir = self.skills_dir / skill.name
        skill_dir.mkdir(exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        try:
            # 检查是否已存在
            cursor = conn.execute(
                "SELECT name FROM generated_skills WHERE name = ?",
                (skill.name,)
            )
            if cursor.fetchone():
                return False, f"Skill已存在: {skill.name}"

            # 保存SKILL.md
            manifest_path = skill_dir / "SKILL.md"
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(skill.to_skill_manifest())

            # 保存适配器
            if skill.adapter_content:
                adapter_path = skill_dir / f"{skill.name}_adapter.py"
                with open(adapter_path, "w", encoding="utf-8") as f:
                    f.write(skill.adapter_content)

            # 保存到数据库
            conn.execute("""
                INSERT INTO generated_skills
                (name, description, version, category, language, source_repo,
                 manifest_content, adapter_content, created_at, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                skill.name, skill.description, skill.version, skill.category,
                skill.language, skill.source_repo,
                skill.to_skill_manifest(), skill.adapter_content,
                skill.created_at, str(skill_dir)
            ))

            conn.commit()
            return True, f"Skill已保存: {skill.name}"

        except Exception as e:
            conn.rollback()
            return False, f"保存失败: {e}"
        finally:
            conn.close()

    def search_by_tags(self, tags: List[str], limit: int = 20) -> List[KnowledgeEntry]:
        """按标签搜索"""
        conn = sqlite3.connect(str(self.db_path))
        entries = []
        try:
            placeholders = ",".join("?" * len(tags))
            cursor = conn.execute(f"""
                SELECT file_path FROM knowledge_entries
                WHERE tags GLOB '*[{placeholders}]*'
                ORDER BY usage_count DESC, created_at DESC
                LIMIT ?
            """, tags + [limit])

            for row in cursor:
                file_path = row[0]
                if Path(file_path).exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        entries.append(KnowledgeEntry.from_dict(data))

            return entries
        finally:
            conn.close()

    def search_by_keyword(self, keyword: str, limit: int = 20) -> List[KnowledgeEntry]:
        """按关键词搜索"""
        conn = sqlite3.connect(str(self.db_path))
        entries = []
        try:
            cursor = conn.execute("""
                SELECT file_path FROM knowledge_entries
                WHERE title LIKE ? OR summary LIKE ? OR content_md LIKE ?
                ORDER BY usage_count DESC, created_at DESC
                LIMIT ?
            """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit))

            for row in cursor:
                file_path = row[0]
                if Path(file_path).exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        entries.append(KnowledgeEntry.from_dict(data))

            return entries
        finally:
            conn.close()

    def increment_usage(self, entry_id: str):
        """增加使用计数"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("UPDATE knowledge_entries SET usage_count = usage_count + 1 WHERE id = ?", (entry_id,))
        conn.commit()
        conn.close()

    def list_all(self, limit: int = 100) -> List[KnowledgeEntry]:
        """列出所有知识条目"""
        conn = sqlite3.connect(str(self.db_path))
        entries = []
        try:
            cursor = conn.execute("""
                SELECT file_path FROM knowledge_entries
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))

            for row in cursor:
                file_path = row[0]
                if Path(file_path).exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        entries.append(KnowledgeEntry.from_dict(data))

            return entries
        finally:
            conn.close()

    def get_stats(self) -> dict:
        """获取统计信息"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            stats = {}

            # 知识条目统计
            cursor = conn.execute("SELECT COUNT(*), SUM(usage_count) FROM knowledge_entries")
            row = cursor.fetchone()
            stats["total_knowledge"] = row[0] or 0
            stats["total_usage"] = row[1] or 0

            # 按类型统计
            cursor = conn.execute("""
                SELECT knowledge_type, COUNT(*) FROM knowledge_entries
                GROUP BY knowledge_type
            """)
            stats["by_type"] = dict(cursor.fetchall())

            # 标签统计
            cursor = conn.execute("SELECT tag, count FROM tag_index ORDER BY count DESC LIMIT 10")
            stats["top_tags"] = dict(cursor.fetchall())

            # Skill统计
            cursor = conn.execute("SELECT COUNT(*) FROM generated_skills")
            stats["total_skills"] = cursor.fetchone()[0] or 0

            return stats
        finally:
            conn.close()
