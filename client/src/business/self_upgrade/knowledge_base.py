# knowledge_base.py — 进化知识库
# 存储辩论结论 + 外部吸收 + 人类修正后的知识

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from .models import KnowledgeEntry, HumanVerdict, SafetyLevel


class KnowledgeBase:
    """
    进化知识库

    存储：
    1. 辩论产生的结论
    2. 外部吸收的洞察
    3. 人类修正后的知识

    支持版本管理和过期机制
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path.home() / ".hermes-desktop" / "self_upgrade"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.data_dir / "knowledge.db"
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                source_debate_id TEXT,
                source_external_id TEXT,
                human_verdict TEXT DEFAULT 'pending',
                version INTEGER DEFAULT 1,
                previous_value TEXT,
                tags TEXT,
                created_at TEXT,
                updated_at TEXT,
                expired_at TEXT,
                UNIQUE(category, key)
            )
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_category ON knowledge_entries(category)
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_key ON knowledge_entries(key)
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_human_verdict ON knowledge_entries(human_verdict)
        """)

        conn.commit()
        conn.close()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    # ============================================================
    # 基础 CRUD
    # ============================================================

    def add(
        self,
        category: str,
        key: str,
        value: str,
        source_debate_id: Optional[str] = None,
        source_external_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        human_verdict: HumanVerdict = HumanVerdict.PENDING,
        expired_at: Optional[datetime] = None,
    ) -> KnowledgeEntry:
        """添加知识条目"""
        entry = KnowledgeEntry(
            id=str(uuid.uuid4()),
            category=category,
            key=key,
            value=value,
            source_debate_id=source_debate_id,
            source_external_id=source_external_id,
            human_verdict=human_verdict,
            tags=tags or [],
            expired_at=expired_at,
        )

        conn = self._conn()
        c = conn.cursor()

        # 检查是否已存在
        c.execute(
            "SELECT id, value FROM knowledge_entries WHERE category=? AND key=?",
            (category, key)
        )
        existing = c.fetchone()

        if existing:
            # 更新现有条目
            old_id, old_value = existing
            entry.id = old_id
            entry.version = self._get_version(category, key) + 1
            entry.previous_value = old_value

            c.execute("""
                UPDATE knowledge_entries
                SET value=?, version=?, previous_value=?, human_verdict=?,
                    updated_at=?, tags=?, expired_at=?
                WHERE id=?
            """, (
                value, entry.version, old_value, human_verdict.value,
                datetime.now().isoformat(),
                json.dumps(tags or [], ensure_ascii=False),
                expired_at.isoformat() if expired_at else None,
                entry.id
            ))
        else:
            c.execute("""
                INSERT INTO knowledge_entries
                (id, category, key, value, source_debate_id, source_external_id,
                 human_verdict, tags, created_at, updated_at, expired_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id, category, key, value,
                source_debate_id, source_external_id,
                human_verdict.value,
                json.dumps(tags or [], ensure_ascii=False),
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                expired_at.isoformat() if expired_at else None,
            ))

        conn.commit()
        conn.close()
        return entry

    def get(self, category: str, key: str) -> Optional[KnowledgeEntry]:
        """获取知识条目"""
        conn = self._conn()
        c = conn.cursor()

        c.execute("""
            SELECT id, category, key, value, source_debate_id, source_external_id,
                   human_verdict, version, previous_value, tags, created_at,
                   updated_at, expired_at
            FROM knowledge_entries
            WHERE category=? AND key=? AND (expired_at IS NULL OR expired_at > ?)
            ORDER BY version DESC
            LIMIT 1
        """, (category, key, datetime.now().isoformat()))

        row = c.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_entry(row)

    def get_all(
        self,
        category: Optional[str] = None,
        verdict: Optional[HumanVerdict] = None,
        limit: int = 100,
    ) -> List[KnowledgeEntry]:
        """获取知识列表"""
        conn = self._conn()
        c = conn.cursor()

        query = "SELECT * FROM knowledge_entries WHERE 1=1"
        params = []

        if category:
            query += " AND category=?"
            params.append(category)

        if verdict:
            query += " AND human_verdict=?"
            params.append(verdict.value)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        return [self._row_to_entry(row) for row in rows]

    def search(self, keyword: str, limit: int = 20) -> List[KnowledgeEntry]:
        """搜索知识"""
        conn = self._conn()
        c = conn.cursor()

        c.execute("""
            SELECT * FROM knowledge_entries
            WHERE (key LIKE ? OR value LIKE ? OR tags LIKE ?)
            ORDER BY updated_at DESC
            LIMIT ?
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit))

        rows = c.fetchall()
        conn.close()
        return [self._row_to_entry(row) for row in rows]

    def update_verdict(
        self,
        entry_id: str,
        verdict: HumanVerdict,
        new_value: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """更新人工裁决"""
        conn = self._conn()
        c = conn.cursor()

        if new_value:
            # 先获取旧值
            c.execute("SELECT value FROM knowledge_entries WHERE id=?", (entry_id,))
            row = c.fetchone()
            if row:
                previous = row[0]
                version = self._get_version_by_id(entry_id) + 1

                c.execute("""
                    UPDATE knowledge_entries
                    SET value=?, version=?, previous_value=?, human_verdict=?,
                        updated_at=?
                    WHERE id=?
                """, (
                    new_value, version, previous, verdict.value,
                    datetime.now().isoformat(), entry_id
                ))
        else:
            c.execute("""
                UPDATE knowledge_entries
                SET human_verdict=?, updated_at=?
                WHERE id=?
            """, (verdict.value, datetime.now().isoformat(), entry_id))

        conn.commit()
        affected = c.rowcount
        conn.close()
        return affected > 0

    def delete(self, entry_id: str) -> bool:
        """删除知识条目"""
        conn = self._conn()
        c = conn.cursor()
        c.execute("DELETE FROM knowledge_entries WHERE id=?", (entry_id,))
        conn.commit()
        affected = c.rowcount
        conn.close()
        return affected > 0

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        conn = self._conn()
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM knowledge_entries")
        total = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM knowledge_entries WHERE human_verdict='approved'")
        approved = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM knowledge_entries WHERE human_verdict='pending'")
        pending = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM knowledge_entries WHERE human_verdict='rejected'")
        rejected = c.fetchone()[0]

        c.execute("SELECT DISTINCT category FROM knowledge_entries")
        categories = [row[0] for row in c.fetchall()]

        conn.close()

        return {
            "total": total,
            "approved": approved,
            "pending": pending,
            "rejected": rejected,
            "categories": categories,
        }

    # ============================================================
    # 辅助方法
    # ============================================================

    def _get_version(self, category: str, key: str) -> int:
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "SELECT MAX(version) FROM knowledge_entries WHERE category=? AND key=?",
            (category, key)
        )
        row = c.fetchone()
        conn.close()
        return row[0] or 0

    def _get_version_by_id(self, entry_id: str) -> int:
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT version FROM knowledge_entries WHERE id=?", (entry_id,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else 0

    def _row_to_entry(self, row: tuple) -> KnowledgeEntry:
        return KnowledgeEntry(
            id=row[0],
            category=row[1],
            key=row[2],
            value=row[3],
            source_debate_id=row[4],
            source_external_id=row[5],
            human_verdict=HumanVerdict(row[6]),
            version=row[7],
            previous_value=row[8] or "",
            tags=json.loads(row[9]) if row[9] else [],
            created_at=datetime.fromisoformat(row[10]),
            updated_at=datetime.fromisoformat(row[11]),
            expired_at=datetime.fromisoformat(row[12]) if row[12] else None,
        )


# 全局单例
_knowledge_base: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
    return _knowledge_base
