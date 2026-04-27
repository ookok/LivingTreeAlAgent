"""
Skill 自进化系统 - 分层记忆数据库

实现 L0-L4 五层记忆的持久化存储
"""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from contextlib import contextmanager

from .models import (
    MemoryLayer,
    MetaRule,
    InsightIndex,
    GlobalFact,
    TaskSkill,
    SessionArchive,
    TaskContext,
    ExecutionRecord,
    ExecutionPhase,
    TaskStatus,
    SkillEvolutionStatus,
    generate_id,
    generate_skill_id,
)


class EvolutionDatabase:
    """
    进化数据库 - 管理 L0-L4 五层记忆

    线程安全，使用 SQLite
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with self._get_conn() as conn:
            conn.executescript("""
                -- L0: Meta Rules 元规则
                CREATE TABLE IF NOT EXISTS meta_rules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    rule_type TEXT DEFAULT 'system',
                    content TEXT NOT NULL,
                    priority INTEGER DEFAULT 0,
                    enabled INTEGER DEFAULT 1,
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    updated_at REAL DEFAULT (strftime('%s', 'now'))
                );

                -- L1: Insight Index 记忆索引
                CREATE TABLE IF NOT EXISTS insight_index (
                    id TEXT PRIMARY KEY,
                    keywords TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    summary TEXT DEFAULT '',
                    embedding_hint TEXT DEFAULT '',
                    access_count INTEGER DEFAULT 0,
                    last_accessed REAL DEFAULT (strftime('%s', 'now')),
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                );

                -- L2: Global Facts 全局事实
                CREATE TABLE IF NOT EXISTS global_facts (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT '',
                    verified INTEGER DEFAULT 0,
                    access_count INTEGER DEFAULT 0,
                    last_accessed REAL DEFAULT (strftime('%s', 'now')),
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    updated_at REAL DEFAULT (strftime('%s', 'now'))
                );

                -- L3: Task Skills 任务技能
                CREATE TABLE IF NOT EXISTS task_skills (
                    skill_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    trigger_patterns TEXT DEFAULT '[]',
                    execution_flow TEXT DEFAULT '[]',
                    tool_sequence TEXT DEFAULT '[]',
                    success_rate REAL DEFAULT 1.0,
                    use_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    avg_duration REAL DEFAULT 0.0,
                    total_duration REAL DEFAULT 0.0,
                    evolution_status TEXT DEFAULT 'seed',
                    version TEXT DEFAULT '1.0.0',
                    parent_skill_id TEXT,
                    prerequisites TEXT DEFAULT '[]',
                    output_schema TEXT DEFAULT '{}',
                    metadata TEXT DEFAULT '{}',
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    last_used REAL DEFAULT (strftime('%s', 'now')),
                    updated_at REAL DEFAULT (strftime('%s', 'now'))
                );

                -- L4: Session Archive 会话归档
                CREATE TABLE IF NOT EXISTS session_archive (
                    id TEXT PRIMARY KEY,
                    task_description TEXT NOT NULL,
                    task_type TEXT DEFAULT '',
                    execution_summary TEXT DEFAULT '',
                    key_insights TEXT DEFAULT '[]',
                    mistakes_made TEXT DEFAULT '[]',
                    lessons_learned TEXT DEFAULT '[]',
                    final_outcome TEXT DEFAULT '',
                    success INTEGER DEFAULT 0,
                    duration REAL DEFAULT 0.0,
                    turns_count INTEGER DEFAULT 0,
                    tools_used TEXT DEFAULT '[]',
                    session_id TEXT DEFAULT '',
                    archived_at REAL DEFAULT (strftime('%s', 'now'))
                );

                -- Task Context 任务上下文（执行中）
                CREATE TABLE IF NOT EXISTS task_context (
                    task_id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    task_type TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    skill_id TEXT,
                    final_result TEXT DEFAULT '',
                    error_message TEXT DEFAULT '',
                    start_time REAL DEFAULT (strftime('%s', 'now')),
                    end_time REAL DEFAULT 0.0,
                    duration REAL DEFAULT 0.0
                );

                -- Execution Records 执行记录
                CREATE TABLE IF NOT EXISTS execution_records (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_args TEXT DEFAULT '{}',
                    tool_result TEXT DEFAULT '',
                    success INTEGER DEFAULT 1,
                    error_msg TEXT DEFAULT '',
                    start_time REAL DEFAULT (strftime('%s', 'now')),
                    end_time REAL DEFAULT 0.0,
                    duration REAL DEFAULT 0.0,
                    FOREIGN KEY (task_id) REFERENCES task_context(task_id)
                );

                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_insight_keywords ON insight_index(keywords);
                CREATE INDEX IF NOT EXISTS idx_insight_layer ON insight_index(layer);
                CREATE INDEX IF NOT EXISTS idx_skill_trigger ON task_skills(trigger_patterns);
                CREATE INDEX IF NOT EXISTS idx_skill_status ON task_skills(evolution_status);
                CREATE INDEX IF NOT EXISTS idx_fact_category ON global_facts(category);
                CREATE INDEX IF NOT EXISTS idx_archive_task_type ON session_archive(task_type);
                CREATE INDEX IF NOT EXISTS idx_record_task ON execution_records(task_id);
            """)

    @contextmanager
    def _get_conn(self):
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ============ L0 Meta Rules ============

    def add_meta_rule(self, rule: MetaRule) -> bool:
        """添加元规则"""
        with self._lock:
            try:
                with self._get_conn() as conn:
                    conn.execute("""
                        INSERT INTO meta_rules (id, name, description, rule_type, content, priority, enabled, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        rule.id, rule.name, rule.description, rule.rule_type,
                        rule.content, rule.priority, rule.enabled,
                        rule.created_at, rule.updated_at
                    ))
                return True
            except sqlite3.IntegrityError:
                return False

    def get_meta_rules(self, enabled_only: bool = True) -> List[MetaRule]:
        """获取元规则"""
        with self._lock:
            with self._get_conn() as conn:
                sql = "SELECT * FROM meta_rules"
                if enabled_only:
                    sql += " WHERE enabled = 1"
                sql += " ORDER BY priority DESC"
                rows = conn.execute(sql).fetchall()
                return [MetaRule(**dict(row)) for row in rows]

    def update_meta_rule(self, rule_id: str, updates: Dict[str, Any]) -> bool:
        """更新元规则"""
        updates['updated_at'] = time.time()
        with self._lock:
            with self._get_conn() as conn:
                set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
                conn.execute(f"UPDATE meta_rules SET {set_clause} WHERE id = ?",
                           (*updates.values(), rule_id))
                return conn.rowcount > 0

    # ============ L1 Insight Index ============

    def add_insight_index(self, index: InsightIndex) -> bool:
        """添加记忆索引"""
        with self._lock:
            try:
                with self._get_conn() as conn:
                    conn.execute("""
                        INSERT INTO insight_index (id, keywords, layer, target_id, summary, embedding_hint, access_count, last_accessed, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        index.id,
                        json.dumps(index.keywords),
                        index.layer.value if isinstance(index.layer, MemoryLayer) else index.layer,
                        index.target_id,
                        index.summary,
                        index.embedding_hint,
                        index.access_count,
                        index.last_accessed,
                        index.created_at
                    ))
                return True
            except sqlite3.IntegrityError:
                return False

    def search_insights(self, query: str, limit: int = 10) -> List[InsightIndex]:
        """搜索记忆索引"""
        keywords = query.lower().split()
        with self._lock:
            with self._get_conn() as conn:
                if keywords:
                    placeholders = " OR ".join(["keywords LIKE ?" for _ in keywords])
                    sql = f"""
                        SELECT * FROM insight_index
                        WHERE {placeholders}
                        ORDER BY access_count DESC
                        LIMIT ?
                    """
                    params = [f"%{kw}%" for kw in keywords] + [limit]
                else:
                    # 空查询时返回最近访问的索引
                    sql = """
                        SELECT * FROM insight_index
                        ORDER BY access_count DESC
                        LIMIT ?
                    """
                    params = [limit]
                rows = conn.execute(sql, params).fetchall()
                results = []
                for row in rows:
                    idx = InsightIndex(**dict(row))
                    idx.keywords = json.loads(row['keywords'])
                    idx.layer = MemoryLayer(row['layer'])
                    results.append(idx)

                for idx in results:
                    conn.execute("UPDATE insight_index SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                               (time.time(), idx.id))
                return results

    def get_insights_by_layer(self, layer: MemoryLayer) -> List[InsightIndex]:
        """按层级获取索引"""
        with self._lock:
            with self._get_conn() as conn:
                layer_val = layer.value if isinstance(layer, MemoryLayer) else layer
                rows = conn.execute(
                    "SELECT * FROM insight_index WHERE layer = ? ORDER BY access_count DESC",
                    (layer_val,)
                ).fetchall()
                results = []
                for row in rows:
                    idx = InsightIndex(**dict(row))
                    idx.keywords = json.loads(row['keywords'])
                    idx.layer = MemoryLayer(row['layer'])
                    results.append(idx)
                return results

    # ============ L2 Global Facts ============

    def add_global_fact(self, fact: GlobalFact) -> bool:
        """添加全局事实"""
        with self._lock:
            try:
                with self._get_conn() as conn:
                    conn.execute("""
                        INSERT INTO global_facts (id, category, content, confidence, source, verified, access_count, last_accessed, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        fact.id, fact.category, fact.content, fact.confidence,
                        fact.source, fact.verified, fact.access_count,
                        fact.last_accessed, fact.created_at, fact.updated_at
                    ))
                return True
            except sqlite3.IntegrityError:
                return False

    def get_global_facts(self, category: Optional[str] = None, verified_only: bool = False) -> List[GlobalFact]:
        """获取全局事实"""
        with self._lock:
            with self._get_conn() as conn:
                sql = "SELECT * FROM global_facts WHERE 1=1"
                params = []
                if category:
                    sql += " AND category = ?"
                    params.append(category)
                if verified_only:
                    sql += " AND verified = 1"
                sql += " ORDER BY access_count DESC, created_at DESC"
                rows = conn.execute(sql, params).fetchall()
                return [GlobalFact(**dict(row)) for row in rows]

    def update_fact(self, fact_id: str, updates: Dict[str, Any]) -> bool:
        """更新事实"""
        updates['updated_at'] = time.time()
        updates['last_accessed'] = time.time()
        with self._lock:
            with self._get_conn() as conn:
                set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
                conn.execute(f"UPDATE global_facts SET {set_clause} WHERE id = ?",
                           (*updates.values(), fact_id))
                return conn.rowcount > 0

    def record_fact_access(self, fact_id: str):
        """记录事实访问"""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE global_facts SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                    (time.time(), fact_id)
                )

    # ============ L3 Task Skills ============

    def add_skill(self, skill: TaskSkill) -> bool:
        """添加技能"""
        with self._lock:
            try:
                with self._get_conn() as conn:
                    conn.execute("""
                        INSERT INTO task_skills (
                            skill_id, name, description, trigger_patterns, execution_flow,
                            tool_sequence, success_rate, use_count, failed_count, avg_duration,
                            total_duration, evolution_status, version, parent_skill_id,
                            prerequisites, output_schema, metadata, created_at, last_used, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        skill.skill_id, skill.name, skill.description,
                        json.dumps(skill.trigger_patterns),
                        json.dumps(skill.execution_flow),
                        json.dumps(skill.tool_sequence),
                        skill.success_rate, skill.use_count, skill.failed_count,
                        skill.avg_duration, skill.total_duration,
                        skill.evolution_status.value if isinstance(skill.evolution_status, SkillEvolutionStatus) else skill.evolution_status,
                        skill.version, skill.parent_skill_id,
                        json.dumps(skill.prerequisites),
                        json.dumps(skill.output_schema),
                        json.dumps(skill.metadata),
                        skill.created_at, skill.last_used, skill.updated_at
                    ))
                return True
            except sqlite3.IntegrityError:
                return False

    def update_skill(self, skill_id: str, updates: Dict[str, Any]) -> bool:
        """更新技能"""
        updates['updated_at'] = time.time()
        with self._lock:
            with self._get_conn() as conn:
                json_fields = {'trigger_patterns', 'execution_flow', 'tool_sequence', 'prerequisites', 'output_schema', 'metadata'}
                set_parts = []
                params = []
                for k, v in updates.items():
                    if k in json_fields:
                        set_parts.append(f"{k} = ?")
                        params.append(json.dumps(v))
                    else:
                        if k == 'evolution_status' and isinstance(v, SkillEvolutionStatus):
                            v = v.value
                        set_parts.append(f"{k} = ?")
                        params.append(v)
                params.append(skill_id)
                conn.execute(f"UPDATE task_skills SET {', '.join(set_parts)} WHERE skill_id = ?", params)
                return conn.rowcount > 0

    def get_skill(self, skill_id: str) -> Optional[TaskSkill]:
        """获取技能"""
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute("SELECT * FROM task_skills WHERE skill_id = ?", (skill_id,)).fetchone()
                if not row:
                    return None
                data = dict(row)
                data['trigger_patterns'] = json.loads(data['trigger_patterns'])
                data['execution_flow'] = json.loads(data['execution_flow'])
                data['tool_sequence'] = json.loads(data['tool_sequence'])
                data['prerequisites'] = json.loads(data['prerequisites'])
                data['output_schema'] = json.loads(data['output_schema'])
                data['metadata'] = json.loads(data['metadata'])
                data['evolution_status'] = SkillEvolutionStatus(data['evolution_status'])
                return TaskSkill(**data)

    def get_all_skills(self, status: Optional[SkillEvolutionStatus] = None) -> List[TaskSkill]:
        """获取所有技能"""
        with self._lock:
            with self._get_conn() as conn:
                sql = "SELECT * FROM task_skills"
                params = []
                if status:
                    sql += " WHERE evolution_status = ?"
                    params.append(status.value if isinstance(status, SkillEvolutionStatus) else status)
                sql += " ORDER BY use_count DESC"
                rows = conn.execute(sql, params).fetchall()
                results = []
                for row in rows:
                    data = dict(row)
                    data['trigger_patterns'] = json.loads(data['trigger_patterns'])
                    data['execution_flow'] = json.loads(data['execution_flow'])
                    data['tool_sequence'] = json.loads(data['tool_sequence'])
                    data['prerequisites'] = json.loads(data['prerequisites'])
                    data['output_schema'] = json.loads(data['output_schema'])
                    data['metadata'] = json.loads(data['metadata'])
                    data['evolution_status'] = SkillEvolutionStatus(data['evolution_status'])
                    results.append(TaskSkill(**data))
                return results

    def find_similar_skills(self, query: str, threshold: float = 0.3) -> List[TaskSkill]:
        """查找相似技能"""
        query_words = set(query.lower().split())
        all_skills = self.get_all_skills()
        results = []

        for skill in all_skills:
            skill_words = set(skill.name.lower().split())
            skill_words.update(skill.description.lower().split())
            for pattern in skill.trigger_patterns:
                skill_words.update(pattern.lower().split())

            if not query_words or not skill_words:
                continue

            intersection = query_words & skill_words
            union = query_words | skill_words
            similarity = len(intersection) / len(union)

            if similarity >= threshold:
                results.append((skill, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return [skill for skill, _ in results]

    def delete_skill(self, skill_id: str) -> bool:
        """删除技能"""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM task_skills WHERE skill_id = ?", (skill_id,))
                return conn.rowcount > 0

    # ============ L4 Session Archive ============

    def add_session_archive(self, archive: SessionArchive) -> bool:
        """添加会话归档"""
        with self._lock:
            try:
                with self._get_conn() as conn:
                    conn.execute("""
                        INSERT INTO session_archive (
                            id, task_description, task_type, execution_summary,
                            key_insights, mistakes_made, lessons_learned,
                            final_outcome, success, duration, turns_count,
                            tools_used, session_id, archived_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        archive.id, archive.task_description, archive.task_type,
                        archive.execution_summary,
                        json.dumps(archive.key_insights),
                        json.dumps(archive.mistakes_made),
                        json.dumps(archive.lessons_learned),
                        archive.final_outcome, archive.success, archive.duration,
                        archive.turns_count, json.dumps(archive.tools_used),
                        archive.session_id, archive.archived_at
                    ))
                return True
            except sqlite3.IntegrityError:
                return False

    def get_recent_archives(self, limit: int = 50) -> List[SessionArchive]:
        """获取最近的归档"""
        with self._lock:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM session_archive ORDER BY archived_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
                results = []
                for row in rows:
                    data = dict(row)
                    data['key_insights'] = json.loads(data['key_insights'])
                    data['mistakes_made'] = json.loads(data['mistakes_made'])
                    data['lessons_learned'] = json.loads(data['lessons_learned'])
                    data['tools_used'] = json.loads(data['tools_used'])
                    results.append(SessionArchive(**data))
                return results

    # ============ Task Context & Execution Records ============

    def create_task_context(self, context: TaskContext) -> bool:
        """创建任务上下文"""
        with self._lock:
            try:
                with self._get_conn() as conn:
                    conn.execute("""
                        INSERT INTO task_context (task_id, description, task_type, status, skill_id, start_time)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        context.task_id, context.description, context.task_type,
                        context.status.value if isinstance(context.status, TaskStatus) else context.status,
                        context.skill_id, context.start_time
                    ))
                return True
            except sqlite3.IntegrityError:
                return False

    def update_task_context(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """更新任务上下文"""
        with self._lock:
            with self._get_conn() as conn:
                status_val = updates.get('status')
                if isinstance(status_val, TaskStatus):
                    updates['status'] = status_val.value
                set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
                conn.execute(f"UPDATE task_context SET {set_clause} WHERE task_id = ?",
                           (*updates.values(), task_id))
                return conn.rowcount > 0

    def add_execution_record(self, record: ExecutionRecord) -> bool:
        """添加执行记录"""
        with self._lock:
            try:
                with self._get_conn() as conn:
                    conn.execute("""
                        INSERT INTO execution_records (
                            id, task_id, phase, tool_name, tool_args, success, start_time
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record.id, record.task_id,
                        record.phase.value if isinstance(record.phase, ExecutionPhase) else record.phase,
                        record.tool_name, json.dumps(record.tool_args),
                        record.success, record.start_time
                    ))
                return True
            except sqlite3.IntegrityError:
                return False

    def finish_execution_record(self, record_id: str, success: bool, error_msg: str = "", result: Any = None):
        """完成执行记录"""
        end_time = time.time()
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute("SELECT start_time FROM execution_records WHERE id = ?", (record_id,)).fetchone()
                if row:
                    duration = end_time - row['start_time']
                    conn.execute("""
                        UPDATE execution_records
                        SET success = ?, error_msg = ?, tool_result = ?, end_time = ?, duration = ?
                        WHERE id = ?
                    """, (success, error_msg, json.dumps(result) if result is not None else '', end_time, duration, record_id))

    def get_task_execution_records(self, task_id: str) -> List[ExecutionRecord]:
        """获取任务的执行记录"""
        with self._lock:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM execution_records WHERE task_id = ? ORDER BY start_time",
                    (task_id,)
                ).fetchall()
                results = []
                for row in rows:
                    data = dict(row)
                    data['tool_args'] = json.loads(data['tool_args'])
                    if data['tool_result']:
                        try:
                            data['tool_result'] = json.loads(data['tool_result'])
                        except:
                            pass
                    data['phase'] = ExecutionPhase(data['phase'])
                    results.append(ExecutionRecord(**data))
                return results

    def get_task_context(self, task_id: str) -> Optional[TaskContext]:
        """获取任务上下文"""
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute("SELECT * FROM task_context WHERE task_id = ?", (task_id,)).fetchone()
                if not row:
                    return None
                data = dict(row)
                data['status'] = TaskStatus(data['status'])
                data['execution_records'] = self.get_task_execution_records(task_id)
                return TaskContext(**data)

    # ============ 统计与维护 ============

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            with self._get_conn() as conn:
                stats = {}
                stats['meta_rules'] = conn.execute("SELECT COUNT(*) FROM meta_rules").fetchone()[0]
                stats['insights'] = conn.execute("SELECT COUNT(*) FROM insight_index").fetchone()[0]
                stats['facts'] = conn.execute("SELECT COUNT(*) FROM global_facts").fetchone()[0]
                stats['skills'] = conn.execute("SELECT COUNT(*) FROM task_skills").fetchone()[0]
                stats['archives'] = conn.execute("SELECT COUNT(*) FROM session_archive").fetchone()[0]
                stats['tasks'] = conn.execute("SELECT COUNT(*) FROM task_context").fetchone()[0]

                status_rows = conn.execute(
                    "SELECT evolution_status, COUNT(*) FROM task_skills GROUP BY evolution_status"
                ).fetchall()
                stats['skills_by_status'] = {row[0]: row[1] for row in status_rows}

                stats['total_skill_uses'] = conn.execute("SELECT SUM(use_count) FROM task_skills").fetchone()[0] or 0

                return stats
