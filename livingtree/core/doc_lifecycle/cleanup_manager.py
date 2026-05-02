"""
清理策略管理器
DocLifecycle 自动化清理系统
"""

import json
import logging
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading

from .models import ActivityLevel, CleanupRule, CleanupStatus, CleanupTask, FileActivity

logger = logging.getLogger(__name__)


class CleanupManager:
    """自动化清理策略管理器"""
    
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
        
        self._archive_dir = Path.home() / ".hermes-desktop" / "archive"
        self._archive_dir.mkdir(parents=True, exist_ok=True)
        
        self._trash_dir = Path.home() / ".hermes-desktop" / ".trash"
        self._trash_dir.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
        self._init_default_rules()
        
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        
        self._callbacks: Dict[str, List] = {
            "cleanup_started": [],
            "cleanup_progress": [],
            "cleanup_completed": [],
            "cleanup_failed": []
        }
        
        self._initialized = True
        logger.info("CleanupManager initialized")
    
    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cleanup_rules (
                rule_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                enabled INTEGER DEFAULT 1,
                min_activity_score REAL DEFAULT 0,
                max_activity_score REAL DEFAULT 100,
                min_file_age_days INTEGER DEFAULT 0,
                max_file_size INTEGER DEFAULT 0,
                allowed_extensions TEXT DEFAULT '[]',
                excluded_extensions TEXT DEFAULT '[]',
                excluded_paths TEXT DEFAULT '[]',
                action TEXT DEFAULT 'archive',
                require_confirmation INTEGER DEFAULT 1,
                notification_enabled INTEGER DEFAULT 1,
                schedule_type TEXT DEFAULT 'daily',
                schedule_time TEXT DEFAULT '02:00',
                notification_before_days INTEGER DEFAULT 7,
                created_at REAL DEFAULT (julianday('now')),
                updated_at REAL DEFAULT (julianday('now'))
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cleanup_tasks (
                task_id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                action TEXT DEFAULT 'archive',
                status TEXT DEFAULT 'pending',
                result TEXT,
                space_freed INTEGER DEFAULT 0,
                executed_at REAL,
                created_at REAL DEFAULT (julianday('now')),
                approved_by TEXT,
                approved_at REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cleanup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                file_size INTEGER,
                space_freed INTEGER,
                executed_at REAL DEFAULT (julianday('now')),
                error_message TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _init_default_rules(self):
        """初始化默认规则"""
        default_rules = [
            CleanupRule(
                rule_id="rule_inactive",
                name="非活跃文件清理",
                description="自动清理长期未访问的文件",
                action="delete",
                require_confirmation=True,
                schedule_type="weekly",
                notification_enabled=True,
                notification_before_days=7
            ),
            CleanupRule(
                rule_id="rule_temp",
                name="临时文件清理",
                description="清理临时文件",
                action="delete",
                require_confirmation=False,
                schedule_type="daily",
                excluded_extensions=['.tmp', '.temp', '~']
            ),
            CleanupRule(
                rule_id="rule_archive",
                name="归档旧文件",
                description="将不常用的文件归档压缩",
                action="compress",
                require_confirmation=True,
                schedule_type="monthly",
                notification_before_days=30
            )
        ]
        
        for rule in default_rules:
            self.add_rule(rule)
    
    def add_rule(self, rule: CleanupRule) -> str:
        """添加清理规则"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO cleanup_rules 
            (rule_id, name, description, enabled, action, require_confirmation,
             notification_enabled, schedule_type, schedule_time, notification_before_days,
             min_activity_score, max_activity_score, min_file_age_days, max_file_size,
             allowed_extensions, excluded_extensions, excluded_paths, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, julianday('now'), julianday('now'))
        """, (
            rule.rule_id, rule.name, rule.description, int(rule.enabled),
            rule.action, int(rule.require_confirmation), int(rule.notification_enabled),
            rule.schedule_type, rule.schedule_time, rule.notification_before_days,
            rule.min_activity_score, rule.max_activity_score, rule.min_file_age_days,
            rule.max_file_size, json.dumps(rule.allowed_extensions),
            json.dumps(rule.excluded_extensions), json.dumps(rule.excluded_paths)
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Added cleanup rule: {rule.name}")
        return rule.rule_id
    
    def get_rules(self, enabled_only: bool = False) -> List[CleanupRule]:
        """获取清理规则"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        query = "SELECT * FROM cleanup_rules"
        if enabled_only:
            query += " WHERE enabled = 1"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        rules = []
        for row in rows:
            rules.append(CleanupRule(
                rule_id=row[0], name=row[1], description=row[2] or "",
                enabled=bool(row[3]),
                min_activity_score=row[4], max_activity_score=row[5],
                min_file_age_days=row[6], max_file_size=row[7],
                allowed_extensions=json.loads(row[8] or "[]"),
                excluded_extensions=json.loads(row[9] or "[]"),
                excluded_paths=json.loads(row[10] or "[]"),
                action=row[11],
                require_confirmation=bool(row[12]),
                notification_enabled=bool(row[13]),
                schedule_type=row[14], schedule_time=row[15],
                notification_before_days=row[16]
            ))
        
        return rules
    
    def delete_rule(self, rule_id: str) -> bool:
        """删除规则"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cleanup_rules WHERE rule_id = ?", (rule_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        logger.info(f"Deleted cleanup rule: {rule_id}")
        return affected > 0
    
    def create_cleanup_tasks(self, activities: List[FileActivity], 
                           dry_run: bool = True) -> List[CleanupTask]:
        """创建清理任务"""
        tasks = []
        rules = self.get_rules(enabled_only=True)
        
        for activity in activities:
            for rule in rules:
                if self._matches_rule(activity, rule):
                    task = CleanupTask(
                        file_path=activity.file_path,
                        file_info=activity,
                        action=rule.action,
                        status="approved" if not rule.require_confirmation else "pending"
                    )
                    tasks.append(task)
                    break
        
        if dry_run:
            logger.info(f"Dry run: {len(tasks)} cleanup tasks created")
        else:
            logger.info(f"{len(tasks)} cleanup tasks created")
        
        return tasks
    
    def _matches_rule(self, activity: FileActivity, rule: CleanupRule) -> bool:
        """检查文件是否匹配规则"""
        if activity.total_score < rule.min_activity_score:
            return False
        if activity.total_score > rule.max_activity_score:
            return False
        
        if rule.min_file_age_days > 0:
            days_since_modified = (datetime.now() - activity.last_modified).days
            if days_since_modified < rule.min_file_age_days:
                return False
        
        if rule.max_file_size > 0 and activity.file_size > rule.max_file_size:
            return False
        
        ext = Path(activity.file_path).suffix.lower()
        excluded = [e.lower() for e in rule.excluded_extensions]
        if ext in excluded or activity.file_name in excluded:
            return False
        
        if rule.allowed_extensions:
            allowed = [e.lower() for e in rule.allowed_extensions]
            if ext not in allowed:
                return False
        
        for excluded_path in rule.excluded_paths:
            if activity.file_path.startswith(excluded_path):
                return False
        
        return True
    
    def execute_cleanup(self, tasks: List[CleanupTask], 
                       dry_run: bool = False) -> Dict[str, Any]:
        """执行清理"""
        result = {
            "total": len(tasks), "success": 0, "failed": 0,
            "space_freed": 0, "errors": []
        }
        
        for task in tasks:
            if task.status in ["cancelled", "completed"]:
                continue
            
            try:
                if dry_run:
                    task.result = "Would execute: " + task.action
                    result["success"] += 1
                    continue
                
                if task.action == "delete":
                    success = self._delete_file(task)
                elif task.action == "archive":
                    success = self._archive_file(task)
                elif task.action == "compress":
                    success = self._compress_file(task)
                elif task.action == "move":
                    success = self._move_file(task)
                else:
                    success = False
                    task.result = f"Unknown action: {task.action}"
                
                if success:
                    task.status = "completed"
                    task.executed_at = datetime.now()
                    result["success"] += 1
                    result["space_freed"] += task.space_freed
                else:
                    task.status = "failed"
                    result["failed"] += 1
                
                self._record_history(task)
                self._emit("cleanup_progress", task)
                
            except Exception as e:
                task.status = "failed"
                task.result = str(e)
                result["failed"] += 1
                result["errors"].append({"task_id": task.task_id, "error": str(e)})
                logger.error(f"Cleanup task failed: {task.task_id}: {e}")
        
        if not dry_run:
            self._emit("cleanup_completed", result)
        
        return result
    
    def _delete_file(self, task: CleanupTask) -> bool:
        """删除文件"""
        file_path = Path(task.file_path)
        
        if not file_path.exists():
            task.result = "File not found"
            return False
        
        trash_path = self._trash_dir / file_path.name
        counter = 1
        while trash_path.exists():
            trash_path = self._trash_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
            counter += 1
        
        shutil.move(str(file_path), str(trash_path))
        
        task.space_freed = file_path.stat().st_size if file_path.exists() else 0
        task.result = f"Moved to trash: {trash_path}"
        
        return True
    
    def _archive_file(self, task: CleanupTask) -> bool:
        """归档文件"""
        file_path = Path(task.file_path)
        
        if not file_path.exists():
            task.result = "File not found"
            return False
        
        archive_date_dir = self._archive_dir / datetime.now().strftime('%Y-%m')
        archive_date_dir.mkdir(parents=True, exist_ok=True)
        
        dest_path = archive_date_dir / file_path.name
        counter = 1
        while dest_path.exists():
            dest_path = archive_date_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
            counter += 1
        
        shutil.move(str(file_path), str(dest_path))
        
        task.space_freed = file_path.stat().st_size if file_path.exists() else 0
        task.result = f"Archived to: {dest_path}"
        
        return True
    
    def _compress_file(self, task: CleanupTask) -> bool:
        """压缩文件"""
        file_path = Path(task.file_path)
        
        if not file_path.exists():
            task.result = "File not found"
            return False
        
        archive_date_dir = self._archive_dir / datetime.now().strftime('%Y-%m') / 'compressed'
        archive_date_dir.mkdir(parents=True, exist_ok=True)
        
        archive_path = archive_date_dir / f"{file_path.stem}.zip"
        counter = 1
        while archive_path.exists():
            archive_path = archive_date_dir / f"{file_path.stem}_{counter}.zip"
            counter += 1
        
        original_size = file_path.stat().st_size
        
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(file_path, file_path.name)
        
        file_path.unlink()
        
        compressed_size = archive_path.stat().st_size
        task.space_freed = original_size - compressed_size
        task.result = f"Compressed to: {archive_path}"
        
        return True
    
    def _move_file(self, task: CleanupTask) -> bool:
        """移动文件"""
        file_path = Path(task.file_path)
        
        if not file_path.exists():
            task.result = "File not found"
            return False
        
        storage_dir = self._archive_dir / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        dest_path = storage_dir / file_path.name
        counter = 1
        while dest_path.exists():
            dest_path = storage_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
            counter += 1
        
        shutil.move(str(file_path), str(dest_path))
        
        task.space_freed = file_path.stat().st_size if file_path.exists() else 0
        task.result = f"Moved to: {dest_path}"
        
        return True
    
    def _record_history(self, task: CleanupTask):
        """记录清理历史"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO cleanup_history 
            (file_path, action, status, file_size, space_freed, executed_at, error_message)
            VALUES (?, ?, ?, ?, ?, julianday('now'), ?)
        """, (
            task.file_path, task.action, task.status,
            task.file_info.file_size if task.file_info else 0,
            task.space_freed,
            task.result if task.status == "failed" else None
        ))
        
        cursor.execute("""
            INSERT OR REPLACE INTO cleanup_tasks
            (task_id, file_path, action, status, result, space_freed, executed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, julianday('now'))
        """, (
            task.task_id, task.file_path, task.action, task.status,
            task.result, task.space_freed, 
            datetime.now().isoformat() if task.executed_at else None
        ))
        
        conn.commit()
        conn.close()
    
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取清理历史"""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM cleanup_history ORDER BY executed_at DESC LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{"id": row[0], "file_path": row[1], "action": row[2],
                 "status": row[3], "file_size": row[4], "space_freed": row[5],
                 "executed_at": row[6], "error_message": row[7]} for row in rows]
    
    def get_trash_contents(self) -> List[Dict[str, Any]]:
        """获取回收站内容"""
        contents = []
        
        if self._trash_dir.exists():
            for file in self._trash_dir.iterdir():
                if file.is_file():
                    stat = file.stat()
                    contents.append({
                        "path": str(file), "name": file.name,
                        "size": stat.st_size,
                        "deleted_at": datetime.fromtimestamp(stat.st_mtime)
                    })
        
        return contents
    
    def restore_from_trash(self, file_path: str) -> bool:
        """从回收站恢复文件"""
        trash_path = Path(file_path)
        
        if not trash_path.exists():
            return False
        
        try:
            original_name = trash_path.name
            original_name = original_name.split('_')[0] if '_' in original_name else original_name
            dest_path = Path.home() / original_name
            
            counter = 1
            while dest_path.exists():
                dest_path = Path.home() / f"{Path(original_name).stem}_{counter}{Path(original_name).suffix}"
                counter += 1
            
            shutil.move(str(trash_path), str(dest_path))
            logger.info(f"Restored from trash: {dest_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore from trash: {e}")
            return False
    
    def register_callback(self, event: str, callback):
        """注册回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _emit(self, event: str, *args):
        """触发事件"""
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    callback(*args)
                except Exception as e:
                    logger.error(f"Callback error for {event}: {e}")
    
    def start_scheduler(self):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        
        logger.info("Cleanup scheduler started")
    
    def stop_scheduler(self):
        """停止调度器"""
        self._running = False
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        
        logger.info("Cleanup scheduler stopped")
    
    def _scheduler_loop(self):
        """调度循环"""
        while self._running:
            try:
                rules = self.get_rules(enabled_only=True)
                for rule in rules:
                    if self._should_execute_rule(rule, datetime.now()):
                        logger.info(f"Executing scheduled rule: {rule.name}")
                threading.Event().wait(3600)
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
    
    def _should_execute_rule(self, rule: CleanupRule, now: datetime) -> bool:
        """检查是否应该执行规则"""
        if rule.schedule_type == "daily":
            return True
        elif rule.schedule_type == "weekly":
            return now.weekday() == 0
        elif rule.schedule_type == "monthly":
            return now.day == 1
        return False


# 全局实例
_cleanup_manager: Optional[CleanupManager] = None


def get_cleanup_manager() -> CleanupManager:
    """获取清理管理器实例"""
    global _cleanup_manager
    if _cleanup_manager is None:
        _cleanup_manager = CleanupManager()
    return _cleanup_manager
