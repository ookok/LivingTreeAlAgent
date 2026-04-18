"""
🌲 生命之树知识林地 (Living Tree Knowledge Grove)
==================================================

行业化智库 × 伪域名阅览厅 × 可迁徙知识包

知识从装配园与使用中生长，按行业聚成林区，供旅人在林间阅览，亦可打包带走或分享。

三层结构：
1. 知识源（装配/用户/网络）→ 沃土库
2. 沃土库（行业标签+内容）→ Wiki渲染
3. Wiki渲染（伪域名/目录树）↔ 导入导出

存储结构：
soil_bank/
├── knowledge/              # 知识条目（现有）
│   ├── entries/           # 按标签分类
│   └── ...
├── industries/             # 🌿 行业索引（新增）
│   ├── electronics.json
│   ├── hardware.json
│   └── ...
├── wiki_cache/            # 🌿 Wiki静态缓存（新增）
│   ├── index.html
│   ├── electronics/
│   └── ...
└── archives/              # 导入导出暂存
"""

import json
import hashlib
import sqlite3
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ==================== 行业林区定义 ====================

class Industry(Enum):
    """行业林区枚举"""
    GENERAL = "general"           # 通用
    ELECTRONICS = "electronics"   # 电子/半导体
    HARDWARE = "hardware"         # 硬件/器件
    SOFTWARE = "software"        # 软件开发
    NETWORK = "network"          # 网络安全
    AI_ML = "ai_ml"             # 人工智能/机器学习
    DATA = "data"               # 数据工程
    CLOUD = "cloud"             # 云计算
    IoT = "iot"                 # 物联网
    AUTOMOTIVE = "automotive"   # 汽车电子
    INDUSTRIAL = "industrial"   # 工业自动化
    MEDICAL = "medical"         # 医疗电子


INDUSTRY_NAMES = {
    "general": "🌐 通用林区",
    "electronics": "💻 电子林区",
    "hardware": "🔧 硬件林区",
    "software": "📝 软件林区",
    "network": "🌐 网络林区",
    "ai_ml": "🤖 AI/ML林区",
    "data": "📊 数据林区",
    "cloud": "☁️ 云服务林区",
    "iot": "📡 物联网林区",
    "automotive": "🚗 汽车林区",
    "industrial": "🏭 工业林区",
    "medical": "🏥 医疗林区",
}


@dataclass
class IndustryIndex:
    """行业索引"""
    id: str                      # 行业ID
    name: str                     # 显示名称
    description: str              # 描述
    icon: str = "🌲"              # 图标
    color: str = "#2a6d39"        # 主题色
    tags: List[str] = field(default_factory=list)  # 关联标签
    entry_count: int = 0          # 条目数量
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'IndustryIndex':
        return cls(**data)


# ==================== 知识条目扩展（支持行业） ====================

@dataclass
class GroveKnowledgeEntry:
    """
    知识林地条目（扩展版）

    在 KnowledgeEntry 基础上增加行业属性
    """
    # 基础字段
    id: str                          # 唯一标识
    title: str                       # 标题
    content_md: str                   # Markdown内容
    summary: str                      # 摘要
    source_url: str = ""              # 来源URL
    source_type: str = "unknown"      # 来源类型

    # 🌿 行业字段
    industries: List[str] = field(default_factory=list)  # 行业林区（可多选）
    tags: List[str] = field(default_factory=list)        # 标签

    # 元数据
    knowledge_type: str = "article"   # 知识类型
    language: str = ""               # 编程语言
    difficulty: str = "intermediate" # 难度
    version: str = "1.0"             # 版本
    created_at: str = ""
    updated_at: str = ""
    usage_count: int = 0            # 调用次数

    # 附件
    attachments: List[str] = field(default_factory=list)  # 关联附件路径

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'GroveKnowledgeEntry':
        return cls(**data)

    def to_markdown(self) -> str:
        """导出为完整Markdown"""
        industries_str = " / ".join(self.industries)
        tags_str = ", ".join(self.tags)

        lines = [
            f"# {self.title}",
            "",
            f"**ID**: `{self.id}`",
            f"**行业**: {industries_str}",
            f"**标签**: {tags_str}",
            f"**类型**: {self.knowledge_type}",
            f"**难度**: {self.difficulty}",
            f"**来源**: [{self.source_url}]({self.source_url})" if self.source_url else "",
            f"**版本**: {self.version}",
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

        if self.attachments:
            lines.extend(["", "---", "", "## 附件"])
            for att in self.attachments:
                lines.append(f"- `{att}`")

        return "\n".join(filter(None, lines))


# ==================== Wiki页面结构 ====================

@dataclass
class WikiPage:
    """Wiki页面"""
    route: str            # 路由路径 (electronics/datasheet_parse)
    title: str             # 页面标题
    content_html: str      # 渲染后的HTML
    entry_id: str          # 对应知识条目ID
    industries: List[str]  # 所属行业
    tags: List[str]        # 标签
    modified_at: str       # 修改时间

    def to_dict(self) -> dict:
        return asdict(self)


# ==================== LTKG包结构 ====================

LTKG_FORMAT_VERSION = "1.0"


@dataclass
class LTKGPackage:
    """LTKG知识包"""
    format_version: str = LTKG_FORMAT_VERSION
    exported_at: str = ""
    exported_by: str = "Hermes Knowledge Grove"
    description: str = ""
    entries: List[dict] = field(default_factory=list)  # 知识条目列表
    files: List[str] = field(default_factory=list)    # 附件文件路径

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'LTKGPackage':
        return cls(**data)


# ==================== 知识林地管理器 ====================

class KnowledgeGrove:
    """
    知识林地管理器

    负责：
    1. 行业索引管理
    2. 知识条目管理（行业感知）
    3. Wiki页面生成
    4. LTKG导入导出
    """

    def __init__(self, base_path: str | Path = None):
        if base_path is None:
            base_path = Path.home() / ".hermes-desktop" / "soil_bank"

        self.base_path = Path(base_path)

        # 目录结构
        self.knowledge_dir = self.base_path / "knowledge" / "entries"
        self.industries_dir = self.base_path / "industries"
        self.wiki_cache_dir = self.base_path / "wiki_cache"
        self.archives_dir = self.base_path / "archives"

        # 创建目录
        self._ensure_directories()

        # 数据库
        self.db_path = self.base_path / "grove.db"

        # 初始化
        self._init_db()
        self._init_industries()

    def _ensure_directories(self):
        """确保目录结构存在"""
        for d in [self.knowledge_dir, self.industries_dir, self.wiki_cache_dir, self.archives_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS industries (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT,
                color TEXT,
                tags TEXT,
                entry_count INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS grove_entries (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT,
                content_md TEXT,
                source_url TEXT,
                source_type TEXT,
                industries TEXT,
                tags TEXT,
                knowledge_type TEXT,
                language TEXT,
                difficulty TEXT,
                version TEXT,
                created_at TEXT,
                updated_at TEXT,
                usage_count INTEGER DEFAULT 0,
                content_hash TEXT UNIQUE,
                file_path TEXT
            );

            CREATE TABLE IF NOT EXISTS wiki_cache (
                route TEXT PRIMARY KEY,
                title TEXT,
                content_html TEXT,
                entry_id TEXT,
                industries TEXT,
                tags TEXT,
                modified_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_grove_industries ON grove_entries(industries);
            CREATE INDEX IF NOT EXISTS idx_grove_tags ON grove_entries(tags);
            CREATE INDEX IF NOT EXISTS idx_wiki_entry ON wiki_cache(entry_id);
        """)
        conn.commit()
        conn.close()

    def _init_industries(self):
        """初始化行业索引"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            # 检查是否已有数据
            cursor = conn.execute("SELECT COUNT(*) FROM industries")
            if cursor.fetchone()[0] > 0:
                return

            # 插入默认行业
            now = datetime.now().isoformat()
            for industry in Industry:
                index = IndustryIndex(
                    id=industry.value,
                    name=INDUSTRY_NAMES.get(industry.value, industry.value),
                    description=f"{industry.value} 行业的知识林区",
                    icon="🌲",
                    color=self._industry_color(industry.value),
                    tags=self._industry_tags(industry.value),
                    created_at=now,
                    updated_at=now
                )
                conn.execute("""
                    INSERT INTO industries (id, name, description, icon, color, tags, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (index.id, index.name, index.description, index.icon, index.color,
                      ",".join(index.tags), index.created_at, index.updated_at))

            conn.commit()
        finally:
            conn.close()

    def _industry_color(self, industry_id: str) -> str:
        """获取行业颜色"""
        colors = {
            "general": "#6b7280",
            "electronics": "#3b82f6",
            "hardware": "#f97316",
            "software": "#8b5cf6",
            "network": "#06b6d4",
            "ai_ml": "#ec4899",
            "data": "#10b981",
            "cloud": "#0ea5e9",
            "iot": "#84cc16",
            "automotive": "#f59e0b",
            "industrial": "#6366f1",
            "medical": "#ef4444",
        }
        return colors.get(industry_id, "#2a6d39")

    def _industry_tags(self, industry_id: str) -> List[str]:
        """获取行业默认标签"""
        tag_map = {
            "electronics": ["pcb", "ic", "semiconductor", "capacitor", "resistor"],
            "hardware": ["cpu", "gpu", "memory", "storage", "sensor"],
            "software": ["python", "javascript", "api", "framework", "architecture"],
            "network": ["tcp", "udp", "http", "dns", "security"],
            "ai_ml": ["neural", "deep_learning", "transformer", "nlp", "cv"],
            "data": ["sql", "nosql", "etl", "pipeline", "analytics"],
            "cloud": ["aws", "azure", "gcp", "kubernetes", "docker"],
            "iot": ["mqtt", "zigbee", "bluetooth", "embedded", "rtos"],
            "automotive": ["can", "lin", "autosar", "adas", "obd"],
            "industrial": ["plc", "scada", "modbus", "industrial_ethernet"],
            "medical": ["medical_device", "fda", "ieee_60601", "biomedical"],
        }
        return tag_map.get(industry_id, [])

    def _generate_id(self, title: str, source_url: str = "") -> str:
        """生成唯一ID"""
        date = datetime.now().strftime("%Y%m%d")
        content = f"{title}:{source_url}:{date}"
        hash8 = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"know_{hash8}_{date}"

    def _content_hash(self, content: str) -> str:
        """计算内容hash"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # ==================== 行业管理 ====================

    def list_industries(self) -> List[IndustryIndex]:
        """列出所有行业"""
        conn = sqlite3.connect(str(self.db_path))
        industries = []
        try:
            cursor = conn.execute("SELECT * FROM industries ORDER BY id")
            for row in cursor:
                data = {
                    "id": row[0], "name": row[1], "description": row[2],
                    "icon": row[3], "color": row[4], "tags": row[5].split(",") if row[5] else [],
                    "entry_count": row[6], "created_at": row[7], "updated_at": row[8]
                }
                industries.append(IndustryIndex.from_dict(data))
            return industries
        finally:
            conn.close()

    def get_industry(self, industry_id: str) -> Optional[IndustryIndex]:
        """获取行业索引"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute("SELECT * FROM industries WHERE id = ?", (industry_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = {
                "id": row[0], "name": row[1], "description": row[2],
                "icon": row[3], "color": row[4], "tags": row[5].split(",") if row[5] else [],
                "entry_count": row[6], "created_at": row[7], "updated_at": row[8]
            }
            return IndustryIndex.from_dict(data)
        finally:
            conn.close()

    def update_industry_count(self, industry_id: str):
        """更新行业条目计数"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM grove_entries WHERE industries LIKE ?",
                (f"%{industry_id}%",)
            )
            count = cursor.fetchone()[0]
            conn.execute(
                "UPDATE industries SET entry_count = ?, updated_at = ? WHERE id = ?",
                (count, datetime.now().isoformat(), industry_id)
            )
            conn.commit()
        finally:
            conn.close()

    # ==================== 知识条目管理 ====================

    def save_entry(self, entry: GroveKnowledgeEntry) -> tuple[bool, str]:
        """
        保存知识林地条目

        Returns:
            (success, message)
        """
        if not entry.id:
            entry.id = self._generate_id(entry.title, entry.source_url)

        now = datetime.now().isoformat()
        if not entry.created_at:
            entry.created_at = now
        entry.updated_at = now

        content_hash = self._content_hash(entry.content_md)

        conn = sqlite3.connect(str(self.db_path))
        try:
            # 检查重复
            cursor = conn.execute(
                "SELECT id FROM grove_entries WHERE content_hash = ?",
                (content_hash,)
            )
            if cursor.fetchone():
                return False, "知识条目内容已存在"

            # 保存文件
            industry = entry.industries[0] if entry.industries else "general"
            entry_dir = self.knowledge_dir / industry
            entry_dir.mkdir(exist_ok=True)

            file_path = entry_dir / f"{entry.id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2)

            # 保存到数据库
            conn.execute("""
                INSERT INTO grove_entries
                (id, title, summary, content_md, source_url, source_type,
                 industries, tags, knowledge_type, language, difficulty, version,
                 created_at, updated_at, content_hash, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id, entry.title, entry.summary, entry.content_md,
                entry.source_url, entry.source_type,
                ",".join(entry.industries), ",".join(entry.tags),
                entry.knowledge_type, entry.language, entry.difficulty, entry.version,
                entry.created_at, entry.updated_at, content_hash, str(file_path)
            ))

            # 更新行业计数
            for ind in entry.industries:
                self.update_industry_count(ind)

            conn.commit()
            return True, f"已保存到 {entry.industries[0] or 'general'} 林区"

        except Exception as e:
            conn.rollback()
            return False, f"保存失败: {e}"
        finally:
            conn.close()

    def get_entry(self, entry_id: str) -> Optional[GroveKnowledgeEntry]:
        """获取知识条目"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute("SELECT file_path FROM grove_entries WHERE id = ?", (entry_id,))
            row = cursor.fetchone()
            if not row:
                return None

            file_path = row[0]
            if Path(file_path).exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    return GroveKnowledgeEntry.from_dict(json.load(f))
            return None
        finally:
            conn.close()

    def list_entries(self, industry: str = None, limit: int = 100) -> List[GroveKnowledgeEntry]:
        """列出知识条目"""
        conn = sqlite3.connect(str(self.db_path))
        entries = []
        try:
            if industry:
                cursor = conn.execute("""
                    SELECT file_path FROM grove_entries
                    WHERE industries LIKE ?
                    ORDER BY created_at DESC LIMIT ?
                """, (f"%{industry}%", limit))
            else:
                cursor = conn.execute("""
                    SELECT file_path FROM grove_entries
                    ORDER BY created_at DESC LIMIT ?
                """, (limit,))

            for row in cursor:
                file_path = row[0]
                if Path(file_path).exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        entries.append(GroveKnowledgeEntry.from_dict(json.load(f)))

            return entries
        finally:
            conn.close()

    def search_entries(self, query: str, industry: str = None, limit: int = 20) -> List[GroveKnowledgeEntry]:
        """搜索知识条目"""
        conn = sqlite3.connect(str(self.db_path))
        entries = []
        try:
            if industry:
                cursor = conn.execute("""
                    SELECT file_path FROM grove_entries
                    WHERE (title LIKE ? OR summary LIKE ? OR content_md LIKE ?)
                      AND industries LIKE ?
                    ORDER BY usage_count DESC, created_at DESC LIMIT ?
                """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{industry}%", limit))
            else:
                cursor = conn.execute("""
                    SELECT file_path FROM grove_entries
                    WHERE title LIKE ? OR summary LIKE ? OR content_md LIKE ?
                    ORDER BY usage_count DESC, created_at DESC LIMIT ?
                """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))

            for row in cursor:
                file_path = row[0]
                if Path(file_path).exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        entries.append(GroveKnowledgeEntry.from_dict(json.load(f)))

            return entries
        finally:
            conn.close()

    def delete_entry(self, entry_id: str) -> tuple[bool, str]:
        """删除知识条目"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute("SELECT industries, file_path FROM grove_entries WHERE id = ?", (entry_id,))
            row = cursor.fetchone()
            if not row:
                return False, "条目不存在"

            industries = row[0].split(",")
            file_path = row[1]

            # 删除文件
            if Path(file_path).exists():
                Path(file_path).unlink()

            # 删除数据库记录
            conn.execute("DELETE FROM grove_entries WHERE id = ?", (entry_id,))
            conn.execute("DELETE FROM wiki_cache WHERE entry_id = ?", (entry_id,))

            # 更新行业计数
            for ind in industries:
                if ind:
                    self.update_industry_count(ind)

            conn.commit()
            return True, "已删除"

        except Exception as e:
            conn.rollback()
            return False, f"删除失败: {e}"
        finally:
            conn.close()

    # ==================== 统计 ====================

    def get_stats(self) -> dict:
        """获取统计信息"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            stats = {}

            # 总体统计
            cursor = conn.execute("SELECT COUNT(*), SUM(usage_count) FROM grove_entries")
            row = cursor.fetchone()
            stats["total_entries"] = row[0] or 0
            stats["total_usage"] = row[1] or 0

            # 行业统计
            cursor = conn.execute("SELECT id, entry_count FROM industries ORDER BY entry_count DESC")
            stats["by_industry"] = {row[0]: row[1] for row in cursor.fetchall()}

            # 类型统计
            cursor = conn.execute("""
                SELECT knowledge_type, COUNT(*) FROM grove_entries
                GROUP BY knowledge_type
            """)
            stats["by_type"] = dict(cursor.fetchall())

            return stats
        finally:
            conn.close()


# ==================== 辅助函数 ====================

def get_grove(base_path: str = None) -> KnowledgeGrove:
    """获取知识林地单例"""
    return KnowledgeGrove(base_path)
