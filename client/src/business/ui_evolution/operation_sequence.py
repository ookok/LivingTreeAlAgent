# -*- coding: utf-8 -*-
"""
操作序列数据库 (Operation Sequence Database)
=============================================

记录和管理用户 UI 操作序列，为预测模型提供训练数据。

核心功能:
- 记录用户操作序列
- 查询相似操作模式
- 统计操作频率
- 支持增量学习数据收集

Author: LivingTreeAI Team
Date: 2026-04-24
"""

import json
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import hashlib


# =============================================================================
# 数据模型
# =============================================================================

@dataclass
class OperationRecord:
    """操作记录"""
    id: Optional[int] = None
    user_id: str = "default"
    action_type: str = ""          # 操作类型: click, input, select, scroll, etc.
    action_target: str = ""         # 操作目标: button_id, input_field, menu_item
    action_value: str = ""          # 操作值: 输入内容、选择项等
    context_features: Dict[str, Any] = field(default_factory=dict)  # 上下文特征
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str = ""
    duration_ms: int = 0           # 操作耗时(毫秒)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action_type": self.action_type,
            "action_target": self.action_target,
            "action_value": self.action_value,
            "context_features": self.context_features,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "duration_ms": self.duration_ms,
        }


@dataclass
class SequencePattern:
    """序列模式"""
    pattern_id: str
    action_sequence: List[str]      # 操作序列: ["click:send_btn", "input:message"]
    frequency: int = 0              # 出现频率
    success_count: int = 0          # 成功次数
    last_used: datetime = field(default_factory=datetime.now)
    next_action: str = ""            # 后续操作
    avg_duration_ms: int = 0        # 平均耗时
    
    @property
    def success_rate(self) -> float:
        if self.frequency == 0:
            return 0.0
        return self.success_count / self.frequency


# =============================================================================
# 操作序列数据库
# =============================================================================

class OperationSequenceDB:
    """
    操作序列数据库
    
    存储用户操作序列，支持：
    - 操作记录 CRUD
    - 序列模式提取
    - 相似模式查询
    - 频率统计
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path.home() / ".hermes-desktop" / "operation_sequence.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._conn: sqlite3.Connection = None
        self._lock = threading.Lock()
        
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        
        # 创建操作记录表
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_target TEXT NOT NULL,
                action_value TEXT DEFAULT '',
                context_features TEXT DEFAULT '{}',
                timestamp TEXT NOT NULL,
                session_id TEXT,
                duration_ms INTEGER DEFAULT 0
            )
        """)
        
        # 创建序列模式表
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sequence_patterns (
                pattern_id TEXT PRIMARY KEY,
                action_sequence TEXT NOT NULL,
                frequency INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                last_used TEXT,
                next_action TEXT DEFAULT '',
                avg_duration_ms INTEGER DEFAULT 0
            )
        """)
        
        # 创建索引
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_user ON operations(user_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_session ON operations(session_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_timestamp ON operations(timestamp)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_pattern_seq ON sequence_patterns(action_sequence)")
        
        self._conn.commit()
    
    def record_operation(self, operation: OperationRecord) -> int:
        """记录一次操作"""
        with self._lock:
            cursor = self._conn.execute("""
                INSERT INTO operations 
                (user_id, action_type, action_target, action_value, context_features, timestamp, session_id, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                operation.user_id,
                operation.action_type,
                operation.action_target,
                operation.action_value,
                json.dumps(operation.context_features, ensure_ascii=False),
                operation.timestamp.isoformat(),
                operation.session_id,
                operation.duration_ms,
            ))
            self._conn.commit()
            return cursor.lastrowid
    
    def get_recent_operations(
        self, 
        user_id: str = "default", 
        session_id: str = None,
        limit: int = 20
    ) -> List[OperationRecord]:
        """获取最近的操作记录"""
        with self._lock:
            query = "SELECT * FROM operations WHERE user_id = ?"
            params: List[Any] = [user_id]
            
            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor = self._conn.execute(query, params)
            return [self._row_to_operation(row) for row in cursor.fetchall()]
    
    def _row_to_operation(self, row: sqlite3.Row) -> OperationRecord:
        """将数据库行转换为 OperationRecord"""
        return OperationRecord(
            id=row["id"],
            user_id=row["user_id"],
            action_type=row["action_type"],
            action_target=row["action_target"],
            action_value=row["action_value"],
            context_features=json.loads(row["context_features"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            session_id=row["session_id"] or "",
            duration_ms=row["duration_ms"],
        )
    
    def get_operation_sequence(
        self, 
        user_id: str = "default",
        session_id: str = None,
        max_length: int = 10
    ) -> List[str]:
        """
        获取操作序列（用于预测）
        
        返回格式: ["click:send_btn", "input:message_field:value"]
        """
        operations = self.get_recent_operations(user_id, session_id, max_length)
        
        # 转换为序列格式
        sequence = []
        for op in reversed(operations):  # 从旧到新
            if op.action_value:
                sequence.append(f"{op.action_type}:{op.action_target}:{op.action_value}")
            else:
                sequence.append(f"{op.action_type}:{op.action_target}")
        
        return sequence
    
    def find_similar_patterns(
        self, 
        current_sequence: List[str],
        user_id: str = "default",
        min_frequency: int = 1
    ) -> List[SequencePattern]:
        """查找相似的序列模式"""
        if not current_sequence:
            return []
        
        # 构建查询序列的哈希
        seq_str = json.dumps(current_sequence[-3:])  # 使用最近3步
        
        with self._lock:
            cursor = self._conn.execute("""
                SELECT * FROM sequence_patterns 
                WHERE frequency >= ? 
                ORDER BY frequency DESC, last_used DESC
                LIMIT 10
            """, (min_frequency,))
            
            patterns = []
            for row in cursor.fetchall():
                pattern = SequencePattern(
                    pattern_id=row["pattern_id"],
                    action_sequence=json.loads(row["action_sequence"]),
                    frequency=row["frequency"],
                    success_count=row["success_count"],
                    last_used=datetime.fromisoformat(row["last_used"]),
                    next_action=row["next_action"],
                    avg_duration_ms=row["avg_duration_ms"],
                )
                patterns.append(pattern)
            
            return patterns
    
    def update_pattern(
        self,
        sequence: List[str],
        next_action: str,
        success: bool = True,
        duration_ms: int = 0
    ):
        """更新序列模式"""
        pattern_id = self._generate_pattern_id(sequence)
        
        with self._lock:
            # 尝试更新现有模式
            cursor = self._conn.execute("""
                UPDATE sequence_patterns 
                SET frequency = frequency + 1,
                    success_count = success_count + ?,
                    last_used = ?,
                    next_action = ?,
                    avg_duration_ms = (avg_duration_ms * frequency + ?) / (frequency + 1)
                WHERE pattern_id = ?
            """, (
                1 if success else 0,
                datetime.now().isoformat(),
                next_action,
                duration_ms,
                pattern_id,
            ))
            
            # 如果不存在，插入新记录
            if cursor.rowcount == 0:
                self._conn.execute("""
                    INSERT INTO sequence_patterns 
                    (pattern_id, action_sequence, frequency, success_count, last_used, next_action, avg_duration_ms)
                    VALUES (?, ?, 1, ?, ?, ?, ?)
                """, (
                    pattern_id,
                    json.dumps(sequence),
                    1 if success else 0,
                    datetime.now().isoformat(),
                    next_action,
                    duration_ms,
                ))
            
            self._conn.commit()
    
    def _generate_pattern_id(self, sequence: List[str]) -> str:
        """生成序列模式 ID"""
        seq_str = json.dumps(sequence[-3:])
        return hashlib.md5(seq_str.encode()).hexdigest()[:12]
    
    def get_operation_stats(self, user_id: str = "default") -> Dict[str, Any]:
        """获取操作统计"""
        with self._lock:
            cursor = self._conn.execute("""
                SELECT 
                    COUNT(*) as total_ops,
                    COUNT(DISTINCT session_id) as sessions,
                    action_type,
                    action_target
                FROM operations 
                WHERE user_id = ?
                GROUP BY action_type, action_target
            """, (user_id,))
            
            stats = defaultdict(lambda: {"count": 0, "targets": defaultdict(int)})
            
            for row in cursor.fetchall():
                action_type = row["action_type"]
                stats[action_type]["count"] += row[0]  # total for this type
                stats[action_type]["targets"][row["action_target"]] = row[0]
            
            return dict(stats)
    
    def get_pattern_stats(self) -> Dict[str, Any]:
        """获取模式统计"""
        with self._lock:
            cursor = self._conn.execute("""
                SELECT COUNT(*) as total_patterns,
                       SUM(frequency) as total_usage,
                       AVG(success_rate) as avg_success
                FROM (
                    SELECT frequency, 
                           CAST(success_count AS FLOAT) / frequency as success_rate
                    FROM sequence_patterns
                )
            """)
            
            row = cursor.fetchone()
            return {
                "total_patterns": row[0] or 0,
                "total_usage": row[1] or 0,
                "avg_success_rate": row[2] or 0.0,
            }
    
    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None


# =============================================================================
# 全局实例
# =============================================================================

_instance: Optional[OperationSequenceDB] = None
_instance_lock = threading.Lock()


def get_operation_db() -> OperationSequenceDB:
    """获取全局操作数据库实例"""
    global _instance
    
    with _instance_lock:
        if _instance is None:
            _instance = OperationSequenceDB()
        return _instance


# =============================================================================
# 便捷函数
# =============================================================================

def record_action(
    action_type: str,
    action_target: str,
    action_value: str = "",
    context: Dict[str, Any] = None,
    session_id: str = None,
    duration_ms: int = 0,
) -> int:
    """
    快速记录一次操作
    
    使用示例:
    ```python
    # 记录点击
    record_action("click", "send_btn", session_id="chat_001")
    
    # 记录输入
    record_action("input", "message_field", "Hello", session_id="chat_001")
    
    # 记录选择
    record_action("select", "model_dropdown", "qwen2.5:1.5b")
    ```
    """
    db = get_operation_db()
    
    operation = OperationRecord(
        action_type=action_type,
        action_target=action_target,
        action_value=action_value,
        context_features=context or {},
        session_id=session_id or "",
        duration_ms=duration_ms,
    )
    
    return db.record_operation(operation)


def get_recent_sequence(max_length: int = 10) -> List[str]:
    """获取最近操作序列"""
    db = get_operation_db()
    return db.get_operation_sequence(max_length=max_length)


def update_sequence_feedback(
    sequence: List[str],
    next_action: str,
    success: bool = True,
    duration_ms: int = 0,
):
    """更新序列模式反馈"""
    db = get_operation_db()
    db.update_pattern(sequence, next_action, success, duration_ms)
