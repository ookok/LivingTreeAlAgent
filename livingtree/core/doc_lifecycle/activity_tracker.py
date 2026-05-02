"""
文件活跃度追踪器
DocLifecycle 文件活跃度评估系统
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import ActivityLevel, FileActivity, FileTier, DocumentType

logger = logging.getLogger(__name__)


class ActivityTracker:
    """文件活跃度追踪器"""
    
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
        logger.info("ActivityTracker initialized")
    
    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        # 访问记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_access_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                access_type TEXT DEFAULT 'read',
                accessed_at REAL DEFAULT (julianday('now')),
                UNIQUE(file_path, accessed_at)
            )
        """)
        
        # 用户标记表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_file_marks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                is_starred INTEGER DEFAULT 0,
                is_critical INTEGER DEFAULT 0,
                tags TEXT DEFAULT '[]',
                marked_at REAL DEFAULT (julianday('now'))
            )
        """)
        
        # 文件关联表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_references (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                target_file TEXT NOT NULL,
                reference_type TEXT DEFAULT 'link',
                created_at REAL DEFAULT (julianday('now')),
                UNIQUE(source_file, target_file)
            )
        """)
        
        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_file ON file_access_logs(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_time ON file_access_logs(accessed_at)")
        
        conn.commit()
        conn.close()
    
    def record_access(self, file_path: str, access_type: str = "read"):
        """记录文件访问"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO file_access_logs (file_path, access_type, accessed_at)
                VALUES (?, ?, julianday('now'))
            """, (file_path, access_type))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to record access: {e}")
    
    def mark_file(self, file_path: str, starred: bool = None, critical: bool = None, 
                  tags: List[str] = None):
        """标记文件"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            
            # 获取现有标记
            cursor.execute("SELECT is_starred, is_critical, tags FROM user_file_marks WHERE file_path = ?",
                          (file_path,))
            row = cursor.fetchone()
            
            is_starred = starred if starred is not None else (row[0] if row else 0)
            is_critical = critical if critical is not None else (row[1] if row else 0)
            existing_tags = set(eval(row[2]) if row and row[2] else [])
            if tags:
                existing_tags.update(tags)
            
            cursor.execute("""
                INSERT OR REPLACE INTO user_file_marks 
                (file_path, is_starred, is_critical, tags, marked_at)
                VALUES (?, ?, ?, ?, julianday('now'))
            """, (file_path, int(is_starred), int(is_critical), str(list(existing_tags))))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to mark file: {e}")
    
    def add_reference(self, source_file: str, target_file: str, ref_type: str = "link"):
        """添加文件引用"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR IGNORE INTO file_references (source_file, target_file, reference_type)
                VALUES (?, ?, ?)
            """, (source_file, target_file, ref_type))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to add reference: {e}")
    
    def evaluate_activity(self, file_path: str) -> FileActivity:
        """评估文件活跃度"""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        stat = path.stat()
        
        # 创建基础活跃度信息
        activity = FileActivity(
            file_path=str(path.absolute()),
            file_name=path.name,
            file_size=stat.st_size,
            file_type=self._detect_type(file_path),
            last_access=datetime.fromtimestamp(stat.st_atime),
            last_modified=datetime.fromtimestamp(stat.st_mtime),
            created_at=datetime.fromtimestamp(stat.st_ctime)
        )
        
        # 计算各个评分
        activity.access_frequency_score = self._calc_access_frequency(file_path)
        activity.recent_access_score = self._calc_recent_access(file_path)
        activity.user_mark_score = self._calc_user_mark_score(file_path)
        activity.relevance_score = self._calc_relevance_score(file_path)
        activity.importance_score = self._calc_importance_score(file_path, activity)
        
        # 计算总分
        activity.total_score = activity.calculate_total_score()
        
        # 确定存储层
        activity.tier = self._determine_tier(activity)
        
        # 获取用户标记
        self._load_user_marks(activity)
        
        # 获取关联信息
        self._load_references(activity)
        
        return activity
    
    def _detect_type(self, file_path: str) -> DocumentType:
        """检测文件类型"""
        ext = Path(file_path).suffix.lower()
        type_map = {
            '.txt': DocumentType.TEXT,
            '.md': DocumentType.MARKDOWN,
            '.pdf': DocumentType.PDF,
            '.doc': DocumentType.DOC,
            '.docx': DocumentType.DOCX,
            '.xls': DocumentType.XLS,
            '.xlsx': DocumentType.XLSX,
            '.csv': DocumentType.CSV,
            '.json': DocumentType.JSON,
            '.xml': DocumentType.XML,
            '.html': DocumentType.HTML,
            '.py': DocumentType.CODE,
            '.js': DocumentType.CODE,
            '.java': DocumentType.CODE,
        }
        return type_map.get(ext, DocumentType.UNKNOWN)
    
    def _calc_access_frequency(self, file_path: str) -> float:
        """计算访问频率分 (25%)"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        # 最近30天的访问次数
        cursor.execute("""
            SELECT COUNT(*) FROM file_access_logs
            WHERE file_path = ? AND accessed_at > julianday('now', '-30 days')
        """, (file_path,))
        count = cursor.fetchone()[0]
        
        conn.close()
        
        # 评分标准
        if count >= 30:  # 每天访问
            return 25.0
        elif count >= 7:  # 每周访问
            return 20.0
        elif count >= 1:  # 每月访问
            return 15.0
        elif count > 0:  # 每季度访问
            return 10.0
        else:  # 半年以上未访问
            return 0.0
    
    def _calc_recent_access(self, file_path: str) -> float:
        """计算最近访问分 (25%)"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        # 获取最近一次访问时间
        cursor.execute("""
            SELECT MAX(accessed_at) FROM file_access_logs WHERE file_path = ?
        """, (file_path,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row or row[0] is None:
            # 如果没有访问记录，使用文件系统的访问时间
            try:
                last_access = Path(file_path).stat().st_atime
                days_ago = (datetime.now() - datetime.fromtimestamp(last_access)).days
            except:
                days_ago = 999
        else:
            # 从julianday转换
            days_ago = (datetime.now() - datetime.fromtimestamp(
                (row[0] - 2440587.5) * 86400
            )).days
        
        if days_ago <= 1:
            return 25.0
        elif days_ago <= 7:
            return 20.0
        elif days_ago <= 30:
            return 15.0
        elif days_ago <= 90:
            return 10.0
        else:
            return 0.0
    
    def _calc_user_mark_score(self, file_path: str) -> float:
        """计算用户标记分 (20%)"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT is_starred, is_critical FROM user_file_marks WHERE file_path = ?
        """, (file_path,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return 5.0  # 无标记
        
        is_starred, is_critical = row
        
        if is_critical:
            return 20.0
        elif is_starred:
            return 15.0
        else:
            return 5.0
    
    def _calc_relevance_score(self, file_path: str) -> float:
        """计算关联性分 (15%)"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        # 被引用次数
        cursor.execute("""
            SELECT COUNT(*) FROM file_references WHERE target_file = ?
        """, (file_path,))
        ref_count = cursor.fetchone()[0]
        
        conn.close()
        
        if ref_count >= 5:
            return 15.0
        elif ref_count >= 2:
            return 12.0
        elif ref_count == 1:
            return 10.0
        elif ref_count == 0:
            return 5.0
        else:
            return 0.0
    
    def _calc_importance_score(self, file_path: str, activity: FileActivity) -> float:
        """计算重要性分 (15%)"""
        path = Path(file_path)
        
        # 系统文件
        system_dirs = ['/etc', '/System', '/Windows', '/Program Files']
        if any(str(path).startswith(d) for d in system_dirs):
            return 15.0
        
        # 配置文件
        if path.suffix in ['.conf', '.cfg', '.ini', '.yaml', '.json']:
            return 12.0
        
        # 代码文件
        if path.suffix in ['.py', '.js', '.java', '.cpp', '.h', '.go', '.rs']:
            return 8.0
        
        # 文档
        if path.suffix in ['.pdf', '.doc', '.docx', '.txt', '.md']:
            return 8.0
        
        # 临时文件
        if path.name.startswith('.') or 'tmp' in path.name.lower():
            return 0.0
        
        return 4.0
    
    def _determine_tier(self, activity: FileActivity) -> FileTier:
        """确定存储层"""
        if activity.activity_level in [ActivityLevel.HIGH, ActivityLevel.MEDIUM_HIGH]:
            return FileTier.ACTIVE
        elif activity.activity_level == ActivityLevel.MEDIUM:
            return FileTier.STORAGE
        else:
            return FileTier.ARCHIVE
    
    def _load_user_marks(self, activity: FileActivity):
        """加载用户标记"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT is_starred, is_critical, tags FROM user_file_marks WHERE file_path = ?
        """, (activity.file_path,))
        row = cursor.fetchone()
        
        if row:
            activity.is_starred = bool(row[0])
            activity.is_critical = bool(row[1])
            try:
                activity.user_tags = eval(row[2]) if row[2] else []
            except:
                activity.user_tags = []
        
        conn.close()
    
    def _load_references(self, activity: FileActivity):
        """加载文件引用"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT source_file FROM file_references WHERE target_file = ?
        """, (activity.file_path,))
        rows = cursor.fetchall()
        activity.referenced_by = [r[0] for r in rows]
        
        conn.close()
    
    def batch_evaluate(self, file_paths: List[str]) -> List[FileActivity]:
        """批量评估文件活跃度"""
        results = []
        for path in file_paths:
            try:
                activity = self.evaluate_activity(path)
                results.append(activity)
            except Exception as e:
                logger.error(f"Failed to evaluate {path}: {e}")
        return results
    
    def get_cleanup_candidates(self, directory: str, 
                               max_activity_score: float = 20) -> List[FileActivity]:
        """获取可清理的文件候选"""
        path = Path(directory)
        if not path.exists():
            return []
        
        candidates = []
        for file_path in path.rglob('*'):
            if not file_path.is_file():
                continue
            
            try:
                activity = self.evaluate_activity(str(file_path))
                if activity.total_score <= max_activity_score:
                    candidates.append(activity)
            except Exception as e:
                logger.error(f"Failed to evaluate {file_path}: {e}")
        
        return sorted(candidates, key=lambda x: x.total_score)
    
    def get_storage_stats(self, directory: str) -> Dict[str, Any]:
        """获取存储统计"""
        path = Path(directory)
        if not path.exists():
            return {}
        
        stats = {
            "total_files": 0,
            "total_size": 0,
            "by_tier": {tier.value: {"count": 0, "size": 0} for tier in FileTier},
            "by_activity": {level.value: {"count": 0, "size": 0} for level in ActivityLevel}
        }
        
        for file_path in path.rglob('*'):
            if not file_path.is_file():
                continue
            
            try:
                activity = self.evaluate_activity(str(file_path))
                stats["total_files"] += 1
                stats["total_size"] += activity.file_size
                stats["by_tier"][activity.tier.value]["count"] += 1
                stats["by_tier"][activity.tier.value]["size"] += activity.file_size
                stats["by_activity"][activity.activity_level.value]["count"] += 1
                stats["by_activity"][activity.activity_level.value]["size"] += activity.file_size
            except Exception:
                pass
        
        return stats


# 全局实例
_tracker: Optional[ActivityTracker] = None


def get_activity_tracker() -> ActivityTracker:
    """获取活跃度追踪器实例"""
    global _tracker
    if _tracker is None:
        _tracker = ActivityTracker()
    return _tracker
