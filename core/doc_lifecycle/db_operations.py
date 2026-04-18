"""
数据库操作模块
DocLifecycle 数据库操作 - SQLite操作封装
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import DocumentInfo, ReportInfo, ReviewResult, ReviewTask, ReviewStatus

logger = logging.getLogger(__name__)


class DBOperations:
    """数据库操作类"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._db_path = Path.home() / ".hermes-desktop" / "doc_lifecycle.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
        self._initialized = True
        
        logger.info(f"DBOperations initialized, db: {self._db_path}")
    
    def _init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        # 文档信息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT DEFAULT 'unknown',
                file_size INTEGER DEFAULT 0,
                hash_value TEXT,
                metadata TEXT DEFAULT '{}',
                created_at REAL,
                modified_at REAL,
                accessed_at REAL
            )
        """)
        
        # 审核任务表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_tasks (
                task_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                review_level TEXT DEFAULT 'standard',
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 5,
                progress REAL DEFAULT 0,
                error_message TEXT,
                result TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at REAL,
                started_at REAL,
                completed_at REAL
            )
        """)
        
        # 审核结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                quality_score REAL DEFAULT 0,
                accuracy_score REAL DEFAULT 0,
                completeness_score REAL DEFAULT 0,
                consistency_score REAL DEFAULT 0,
                clarity_score REAL DEFAULT 0,
                professionalism_score REAL DEFAULT 0,
                innovation_score REAL DEFAULT 0,
                issues TEXT DEFAULT '[]',
                suggestions TEXT DEFAULT '[]',
                category TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                summary TEXT DEFAULT '',
                processing_time REAL DEFAULT 0,
                sensitive_words_found TEXT DEFAULT '[]',
                risk_level TEXT DEFAULT 'low',
                created_at REAL
            )
        """)
        
        # 报告表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                task_id TEXT,
                doc_id TEXT,
                report_type TEXT DEFAULT 'single',
                report_format TEXT DEFAULT 'html',
                file_path TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                title TEXT,
                download_count INTEGER DEFAULT 0,
                active_score REAL DEFAULT 100,
                retention_policy TEXT DEFAULT 'default',
                clean_status TEXT DEFAULT 'normal',
                created_at REAL,
                last_access REAL
            )
        """)
        
        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_path ON documents(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON review_tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_doc ON review_tasks(doc_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_task ON review_results(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_doc ON reports(doc_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at)")
        
        conn.commit()
        conn.close()
    
    # ==================== 文档操作 ====================
    
    def save_document(self, doc_info: DocumentInfo) -> bool:
        """保存文档信息"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO documents
                (doc_id, file_path, file_name, file_type, file_size, hash_value,
                 metadata, created_at, modified_at, accessed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_info.doc_id,
                doc_info.file_path,
                doc_info.file_name,
                doc_info.file_type.value,
                doc_info.file_size,
                doc_info.hash_value,
                json.dumps(doc_info.metadata),
                doc_info.created_at.timestamp(),
                doc_info.modified_at.timestamp(),
                doc_info.accessed_at.timestamp()
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            return False
    
    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        """获取文档信息"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        from .models import DocumentType
        return DocumentInfo(
            doc_id=row[0], file_path=row[1], file_name=row[2],
            file_type=DocumentType(row[3]),
            file_size=row[4], hash_value=row[5],
            metadata=json.loads(row[6] or "{}"),
            created_at=datetime.fromtimestamp(row[7]) if row[7] else datetime.now(),
            modified_at=datetime.fromtimestamp(row[8]) if row[8] else datetime.now(),
            accessed_at=datetime.fromtimestamp(row[9]) if row[9] else datetime.now()
        )
    
    def get_documents(self, limit: int = 100, offset: int = 0) -> List[DocumentInfo]:
        """获取文档列表"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM documents ORDER BY modified_at DESC LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        from .models import DocumentType
        return [
            DocumentInfo(
                doc_id=row[0], file_path=row[1], file_name=row[2],
                file_type=DocumentType(row[3]),
                file_size=row[4], hash_value=row[5],
                metadata=json.loads(row[6] or "{}"),
                created_at=datetime.fromtimestamp(row[7]) if row[7] else datetime.now(),
                modified_at=datetime.fromtimestamp(row[8]) if row[8] else datetime.now(),
                accessed_at=datetime.fromtimestamp(row[9]) if row[9] else datetime.now()
            )
            for row in rows
        ]
    
    def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0
    
    # ==================== 审核任务操作 ====================
    
    def save_task(self, task: ReviewTask) -> bool:
        """保存审核任务"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO review_tasks
                (task_id, doc_id, review_level, status, priority, progress,
                 error_message, result, retry_count, max_retries,
                 created_at, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id, task.doc_id, task.review_level.value,
                task.status.value, task.priority, task.progress,
                task.error_message, json.dumps(task.result) if task.result else None,
                task.retry_count, task.max_retries,
                task.created_at.timestamp() if task.created_at else datetime.now().timestamp(),
                task.started_at.timestamp() if task.started_at else None,
                task.completed_at.timestamp() if task.completed_at else None
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to save task: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[ReviewTask]:
        """获取审核任务"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM review_tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        from .models import ReviewLevel as RL, ReviewStatus as RS
        
        return ReviewTask(
            task_id=row[0], doc_id=row[1],
            review_level=RL(row[2]), status=RS(row[3]),
            priority=row[4], progress=row[5] or 0,
            error_message=row[6] or "",
            result=json.loads(row[7]) if row[7] else None,
            retry_count=row[8], max_retries=row[9],
            created_at=datetime.fromtimestamp(row[10]) if row[10] else datetime.now(),
            started_at=datetime.fromtimestamp(row[11]) if row[11] else None,
            completed_at=datetime.fromtimestamp(row[12]) if row[12] else None
        )
    
    def get_tasks(self, status: Optional[ReviewStatus] = None,
                  limit: int = 100) -> List[ReviewTask]:
        """获取审核任务列表"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT * FROM review_tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?
            """, (status.value, limit))
        else:
            cursor.execute("""
                SELECT * FROM review_tasks ORDER BY created_at DESC LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        from .models import ReviewLevel as RL, ReviewStatus as RS
        
        return [
            ReviewTask(
                task_id=row[0], doc_id=row[1],
                review_level=RL(row[2]), status=RS(row[3]),
                priority=row[4], progress=row[5] or 0,
                error_message=row[6] or "",
                result=json.loads(row[7]) if row[7] else None,
                retry_count=row[8], max_retries=row[9],
                created_at=datetime.fromtimestamp(row[10]) if row[10] else datetime.now(),
                started_at=datetime.fromtimestamp(row[11]) if row[11] else None,
                completed_at=datetime.fromtimestamp(row[12]) if row[12] else None
            )
            for row in rows
        ]
    
    # ==================== 审核结果操作 ====================
    
    def save_result(self, result: ReviewResult) -> bool:
        """保存审核结果"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO review_results
                (task_id, doc_id, quality_score, accuracy_score, completeness_score,
                 consistency_score, clarity_score, professionalism_score, innovation_score,
                 issues, suggestions, category, tags, summary, processing_time,
                 sensitive_words_found, risk_level, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.task_id, result.doc_id, result.quality_score,
                result.accuracy_score, result.completeness_score,
                result.consistency_score, result.clarity_score,
                result.professionalism_score, result.innovation_score,
                json.dumps(result.issues), json.dumps(result.suggestions),
                result.category, json.dumps(result.tags), result.summary,
                result.processing_time, json.dumps(result.sensitive_words_found),
                result.risk_level, result.created_at.timestamp()
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to save result: {e}")
            return False
    
    def get_result(self, task_id: str) -> Optional[ReviewResult]:
        """获取审核结果"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM review_results WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return ReviewResult(
            task_id=row[1], doc_id=row[2], quality_score=row[3] or 0,
            accuracy_score=row[4] or 0, completeness_score=row[5] or 0,
            consistency_score=row[6] or 0, clarity_score=row[7] or 0,
            professionalism_score=row[8] or 0, innovation_score=row[9] or 0,
            issues=json.loads(row[10] or "[]"),
            suggestions=json.loads(row[11] or "[]"),
            category=row[12] or "", tags=json.loads(row[13] or "[]"),
            summary=row[14] or "", processing_time=row[15] or 0,
            sensitive_words_found=json.loads(row[16] or "[]"),
            risk_level=row[17] or "low",
            created_at=datetime.fromtimestamp(row[18]) if row[18] else datetime.now()
        )
    
    def get_results(self, doc_id: Optional[str] = None,
                   limit: int = 100) -> List[ReviewResult]:
        """获取审核结果列表"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        if doc_id:
            cursor.execute("""
                SELECT * FROM review_results WHERE doc_id = ? ORDER BY created_at DESC LIMIT ?
            """, (doc_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM review_results ORDER BY created_at DESC LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            ReviewResult(
                task_id=row[1], doc_id=row[2], quality_score=row[3] or 0,
                accuracy_score=row[4] or 0, completeness_score=row[5] or 0,
                consistency_score=row[6] or 0, clarity_score=row[7] or 0,
                professionalism_score=row[8] or 0, innovation_score=row[9] or 0,
                issues=json.loads(row[10] or "[]"),
                suggestions=json.loads(row[11] or "[]"),
                category=row[12] or "", tags=json.loads(row[13] or "[]"),
                summary=row[14] or "", processing_time=row[15] or 0,
                sensitive_words_found=json.loads(row[16] or "[]"),
                risk_level=row[17] or "low",
                created_at=datetime.fromtimestamp(row[18]) if row[18] else datetime.now()
            )
            for row in rows
        ]
    
    # ==================== 报告操作 ====================
    
    def save_report(self, report: ReportInfo) -> bool:
        """保存报告信息"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO reports
                (report_id, task_id, doc_id, report_type, report_format, file_path,
                 file_size, title, download_count, active_score, retention_policy,
                 clean_status, created_at, last_access)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report.report_id, report.task_id, report.doc_id,
                report.report_type, report.report_format, report.file_path,
                report.file_size, report.title, report.download_count,
                report.active_score, report.retention_policy,
                report.clean_status.value,
                report.created_at.timestamp(),
                report.last_access.timestamp()
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            return False
    
    def get_reports(self, doc_id: Optional[str] = None,
                   limit: int = 100) -> List[ReportInfo]:
        """获取报告列表"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        if doc_id:
            cursor.execute("""
                SELECT * FROM reports WHERE doc_id = ? ORDER BY created_at DESC LIMIT ?
            """, (doc_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM reports ORDER BY created_at DESC LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        from .models import CleanupStatus as CS
        
        return [
            ReportInfo(
                report_id=row[0], task_id=row[1], doc_id=row[2],
                report_type=row[3], report_format=row[4], file_path=row[5],
                file_size=row[6], title=row[7], download_count=row[8] or 0,
                active_score=row[9] or 100, retention_policy=row[10] or "default",
                clean_status=CS(row[11]),
                created_at=datetime.fromtimestamp(row[12]) if row[12] else datetime.now(),
                last_access=datetime.fromtimestamp(row[13]) if row[13] else datetime.now()
            )
            for row in rows
        ]
    
    def increment_download_count(self, report_id: str) -> bool:
        """增加下载次数"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE reports SET download_count = download_count + 1 WHERE report_id = ?
        """, (report_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0
    
    # ==================== 统计操作 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        stats = {}
        
        # 文档数
        cursor.execute("SELECT COUNT(*) FROM documents")
        stats["total_documents"] = cursor.fetchone()[0]
        
        # 任务统计
        cursor.execute("SELECT COUNT(*) FROM review_tasks")
        stats["total_tasks"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM review_tasks WHERE status = ?", 
                      (ReviewStatus.COMPLETED.value,))
        stats["completed_tasks"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM review_tasks WHERE status = ?",
                      (ReviewStatus.PROCESSING.value,))
        stats["processing_tasks"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM review_tasks WHERE status = ?",
                      (ReviewStatus.FAILED.value,))
        stats["failed_tasks"] = cursor.fetchone()[0]
        
        # 平均质量分
        cursor.execute("SELECT AVG(quality_score) FROM review_results")
        avg = cursor.fetchone()[0]
        stats["avg_quality_score"] = round(avg, 1) if avg else 0
        
        # 报告数
        cursor.execute("SELECT COUNT(*) FROM reports")
        stats["total_reports"] = cursor.fetchone()[0]
        
        conn.close()
        return stats


# 全局实例
_db_ops: Optional[DBOperations] = None


def get_db_operations() -> DBOperations:
    """获取数据库操作实例"""
    global _db_ops
    if _db_ops is None:
        _db_ops = DBOperations()
    return _db_ops
