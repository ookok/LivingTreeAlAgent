# evolution_log.py - 进化日志（SQLite 持久化存储）

"""
Evolution Log - 记录每次扫描、提案、执行的结果

核心功能：
1. 记录每次传感器扫描的信号
2. 记录每次提案的生成和状态变更
3. 记录每次执行的结果和回滚
4. 支持历史查询和统计分析
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from threading import Lock
import threading

logger = logging.getLogger('evolution.log')


@dataclass
class ScanRecord:
    """扫描记录"""
    id: Optional[int] = None
    timestamp: str = ""
    sensor_type: str = ""
    signals_count: int = 0
    signals_summary: str = ""  # JSON 摘要
    duration_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProposalRecord:
    """提案记录"""
    id: Optional[int] = None
    proposal_id: str = ""
    timestamp: str = ""
    proposal_type: str = ""
    priority: str = ""
    risk_level: str = ""
    status: str = ""
    title: str = ""
    description: str = ""
    signals_summary: str = ""  # 触发的信号
    estimated_impact: str = ""
    actual_impact: str = ""  # 执行后的实际影响
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionRecord:
    """执行记录"""
    id: Optional[int] = None
    proposal_id: str = ""
    timestamp: str = ""
    status: str = ""  # success, failed, rolled_back
    steps_completed: int = 0
    steps_total: int = 0
    duration_ms: float = 0.0
    error_message: str = ""
    rollback_id: Optional[str] = None
    git_branch: str = ""
    git_commit: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionRecord:
    """决策记录"""
    id: Optional[int] = None
    timestamp: str = ""
    decision_type: str = ""  # approve, reject, rollback, adjust
    target_id: str = ""  # proposal_id 或 execution_id
    reason: str = ""
    factors: str = ""  # JSON 数组，影响决策的因素
    outcome: str = ""  # 决策结果
    feedback: str = ""  # 后续反馈
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvolutionLog:
    """
    进化日志管理器
    
    使用 SQLite 持久化存储所有进化相关数据
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, db_path: Optional[str] = None):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._db_path = db_path or self._get_default_db_path()
        self._conn: Optional[sqlite3.Connection] = None
        self._conn_lock = Lock()
        
        self._init_database()
        logger.info(f"[EvolutionLog] 初始化完成，数据库: {self._db_path}")
    
    @staticmethod
    def _get_default_db_path() -> str:
        """获取默认数据库路径"""
        from .evolution_engine import EvolutionEngine
        # 在项目根目录下创建 .evolution_db 目录
        project_root = Path.cwd()
        db_dir = project_root / '.evolution_db'
        db_dir.mkdir(exist_ok=True)
        return str(db_dir / 'evolution_log.db')
    
    def _init_database(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 扫描记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scan_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    sensor_type TEXT NOT NULL,
                    signals_count INTEGER DEFAULT 0,
                    signals_summary TEXT,
                    duration_ms REAL DEFAULT 0.0
                )
            ''')
            
            # 提案记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS proposal_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id TEXT UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    proposal_type TEXT,
                    priority TEXT,
                    risk_level TEXT,
                    status TEXT,
                    title TEXT,
                    description TEXT,
                    signals_summary TEXT,
                    estimated_impact TEXT,
                    actual_impact TEXT
                )
            ''')
            
            # 执行记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS execution_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT,
                    steps_completed INTEGER DEFAULT 0,
                    steps_total INTEGER DEFAULT 0,
                    duration_ms REAL DEFAULT 0.0,
                    error_message TEXT,
                    rollback_id TEXT,
                    git_branch TEXT,
                    git_commit TEXT
                )
            ''')
            
            # 决策记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS decision_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    target_id TEXT,
                    reason TEXT,
                    factors TEXT,
                    outcome TEXT,
                    feedback TEXT
                )
            ''')
            
            # 信号记录表（原始信号数据）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signal_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id INTEGER,
                    timestamp TEXT NOT NULL,
                    sensor_type TEXT,
                    signal_type TEXT,
                    severity TEXT,
                    location TEXT,
                    description TEXT,
                    metrics TEXT,
                    FOREIGN KEY (scan_id) REFERENCES scan_records(id)
                )
            ''')
            
            # 提案步骤记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS step_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id INTEGER,
                    step_index INTEGER,
                    step_type TEXT,
                    description TEXT,
                    status TEXT,
                    duration_ms REAL DEFAULT 0.0,
                    error TEXT,
                    FOREIGN KEY (execution_id) REFERENCES execution_records(id)
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_timestamp ON scan_records(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_proposal_id ON proposal_records(proposal_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_proposal_status ON proposal_records(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_execution_status ON execution_records(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_signal_scan ON signal_records(scan_id)')
            
            conn.commit()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接（线程安全）"""
        with self._conn_lock:
            if self._conn is None:
                self._conn = sqlite3.connect(
                    self._db_path,
                    check_same_thread=False,
                    timeout=30.0
                )
                self._conn.row_factory = sqlite3.Row
            return self._conn
    
    # ========== 扫描记录 ==========
    
    def log_scan(
        self,
        sensor_type: str,
        signals_count: int,
        signals_summary: Dict[str, Any],
        duration_ms: float
    ) -> int:
        """记录一次扫描"""
        timestamp = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO scan_records (timestamp, sensor_type, signals_count, signals_summary, duration_ms)
                VALUES (?, ?, ?, ?, ?)
            ''', (timestamp, sensor_type, signals_count, json.dumps(signals_summary), duration_ms))
            conn.commit()
            
            scan_id = cursor.lastrowid
            
            # 记录原始信号
            for signal in signals_summary.get('signals', []):
                cursor.execute('''
                    INSERT INTO signal_records 
                    (scan_id, timestamp, sensor_type, signal_type, severity, location, description, metrics)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    scan_id,
                    timestamp,
                    sensor_type,
                    signal.get('type', ''),
                    signal.get('severity', ''),
                    signal.get('location', ''),
                    signal.get('description', ''),
                    json.dumps(signal.get('metrics', {}))
                ))
            
            conn.commit()
            return scan_id
    
    def get_recent_scans(self, limit: int = 10) -> List[ScanRecord]:
        """获取最近的扫描记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM scan_records ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
            
            return [
                ScanRecord(
                    id=row['id'],
                    timestamp=row['timestamp'],
                    sensor_type=row['sensor_type'],
                    signals_count=row['signals_count'],
                    signals_summary=row['signals_summary'],
                    duration_ms=row['duration_ms']
                )
                for row in cursor.fetchall()
            ]
    
    # ========== 提案记录 ==========
    
    def log_proposal(self, proposal) -> int:
        """记录提案（接受 StructuredProposal 对象）"""
        timestamp = datetime.now().isoformat()
        
        # 提取信号摘要
        signals_summary = []
        if hasattr(proposal, 'trigger_signals') and proposal.trigger_signals:
            for signal in proposal.trigger_signals:
                signals_summary.append({
                    'type': signal.type.value if hasattr(signal.type, 'value') else str(signal.type),
                    'severity': signal.severity,
                    'location': signal.location,
                    'description': signal.description
                })
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO proposal_records 
                (proposal_id, timestamp, proposal_type, priority, risk_level, status, 
                 title, description, signals_summary, estimated_impact, actual_impact)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                proposal.proposal_id,
                timestamp,
                proposal.proposal_type.value if hasattr(proposal.proposal_type, 'value') else str(proposal.proposal_type),
                proposal.priority.value if hasattr(proposal.priority, 'value') else str(proposal.priority),
                proposal.risk_level.value if hasattr(proposal.risk_level, 'value') else str(proposal.risk_level),
                proposal.status.value if hasattr(proposal.status, 'value') else str(proposal.status),
                proposal.title,
                proposal.description,
                json.dumps(signals_summary),
                proposal.estimated_impact,
                getattr(proposal, 'actual_impact', '')
            ))
            conn.commit()
            return cursor.lastrowid
    
    def update_proposal_status(self, proposal_id: str, status: str, actual_impact: str = ''):
        """更新提案状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE proposal_records 
                SET status = ?, actual_impact = ?
                WHERE proposal_id = ?
            ''', (status, actual_impact, proposal_id))
            conn.commit()
    
    def get_proposals_by_status(self, status: str, limit: int = 50) -> List[ProposalRecord]:
        """按状态获取提案"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM proposal_records 
                WHERE status = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (status, limit))
            
            return [self._row_to_proposal(row) for row in cursor.fetchall()]
    
    def get_all_proposals(self, limit: int = 100) -> List[ProposalRecord]:
        """获取所有提案"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM proposal_records ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
            
            return [self._row_to_proposal(row) for row in cursor.fetchall()]
    
    def _row_to_proposal(self, row: sqlite3.Row) -> ProposalRecord:
        return ProposalRecord(
            id=row['id'],
            proposal_id=row['proposal_id'],
            timestamp=row['timestamp'],
            proposal_type=row['proposal_type'],
            priority=row['priority'],
            risk_level=row['risk_level'],
            status=row['status'],
            title=row['title'],
            description=row['description'],
            signals_summary=row['signals_summary'],
            estimated_impact=row['estimated_impact'],
            actual_impact=row['actual_impact']
        )
    
    # ========== 执行记录 ==========
    
    def log_execution(self, execution_result: Dict[str, Any]) -> int:
        """记录执行结果"""
        timestamp = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO execution_records 
                (proposal_id, timestamp, status, steps_completed, steps_total, 
                 duration_ms, error_message, rollback_id, git_branch, git_commit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                execution_result.get('proposal_id', ''),
                timestamp,
                execution_result.get('status', ''),
                execution_result.get('steps_completed', 0),
                execution_result.get('steps_total', 0),
                execution_result.get('duration_ms', 0),
                execution_result.get('error', ''),
                execution_result.get('rollback_id'),
                execution_result.get('git_branch', ''),
                execution_result.get('git_commit', '')
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 总数
            cursor.execute('SELECT COUNT(*) as total FROM execution_records')
            total = cursor.fetchone()['total']
            
            # 按状态统计
            cursor.execute('''
                SELECT status, COUNT(*) as count 
                FROM execution_records 
                GROUP BY status
            ''')
            by_status = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # 平均执行时间
            cursor.execute('SELECT AVG(duration_ms) as avg_duration FROM execution_records')
            avg_duration = cursor.fetchone()['avg_duration'] or 0
            
            # 成功率
            success_count = by_status.get('success', 0)
            success_rate = success_count / total * 100 if total > 0 else 0
            
            return {
                'total': total,
                'by_status': by_status,
                'avg_duration_ms': avg_duration,
                'success_rate': success_rate
            }
    
    # ========== 决策记录 ==========
    
    def log_decision(
        self,
        decision_type: str,
        target_id: str,
        reason: str,
        factors: List[str],
        outcome: str = '',
        feedback: str = ''
    ) -> int:
        """记录决策"""
        timestamp = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO decision_records 
                (timestamp, decision_type, target_id, reason, factors, outcome, feedback)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp,
                decision_type,
                target_id,
                reason,
                json.dumps(factors),
                outcome,
                feedback
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_decisions_by_type(self, decision_type: str, limit: int = 50) -> List[DecisionRecord]:
        """按类型获取决策"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM decision_records 
                WHERE decision_type = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (decision_type, limit))
            
            return [self._row_to_decision(row) for row in cursor.fetchall()]
    
    def _row_to_decision(self, row: sqlite3.Row) -> DecisionRecord:
        return DecisionRecord(
            id=row['id'],
            timestamp=row['timestamp'],
            decision_type=row['decision_type'],
            target_id=row['target_id'],
            reason=row['reason'],
            factors=row['factors'],
            outcome=row['outcome'],
            feedback=row['feedback']
        )
    
    # ========== 统计和分析 ==========
    
    def get_summary(self) -> Dict[str, Any]:
        """获取进化统计摘要"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 扫描次数
            cursor.execute('SELECT COUNT(*) FROM scan_records')
            total_scans = cursor.fetchone()[0]
            
            # 提案数
            cursor.execute('SELECT COUNT(*) FROM proposal_records')
            total_proposals = cursor.fetchone()[0]
            
            # 执行数
            execution_stats = self.get_execution_stats()
            
            # 决策数
            cursor.execute('SELECT COUNT(*) FROM decision_records')
            total_decisions = cursor.fetchone()[0]
            
            return {
                'total_scans': total_scans,
                'total_proposals': total_proposals,
                'total_executions': execution_stats['total'],
                'execution_success_rate': execution_stats['success_rate'],
                'total_decisions': total_decisions,
                'db_path': self._db_path
            }
    
    def get_signal_trends(self, days: int = 7) -> Dict[str, Any]:
        """获取信号趋势"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 按天统计信号
            cursor.execute('''
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM scan_records
                WHERE timestamp >= datetime('now', ?)
                GROUP BY DATE(timestamp)
                ORDER BY date
            ''', (f'-{days} days',))
            
            daily_counts = {row['date']: row['count'] for row in cursor.fetchall()}
            
            # 按严重程度统计
            cursor.execute('''
                SELECT severity, COUNT(*) as count
                FROM signal_records
                GROUP BY severity
            ''')
            by_severity = {row['severity']: row['count'] for row in cursor.fetchall()}
            
            return {
                'daily_counts': daily_counts,
                'by_severity': by_severity
            }
    
    def close(self):
        """关闭数据库连接"""
        with self._conn_lock:
            if self._conn:
                self._conn.close()
                self._conn = None


# 全局单例
_evolution_log: Optional[EvolutionLog] = None


def get_evolution_log(db_path: Optional[str] = None) -> EvolutionLog:
    """获取 EvolutionLog 单例"""
    global _evolution_log
    if _evolution_log is None:
        _evolution_log = EvolutionLog(db_path)
    return _evolution_log
