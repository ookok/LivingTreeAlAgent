"""
消息模式管理器
Message Pattern Manager - CRUD, Storage, Import/Export
"""

import json
import sqlite3
import os
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from pathlib import Path
import threading
import shutil

from .models import (
    MessagePattern, PatternCategory, TriggerType, 
    BuiltInPatterns, PatternMetadata, PatternUsageRecord
)


class PatternDatabase:
    """模式数据库操作"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = os.path.join(os.path.expanduser("~"), ".hermes-desktop", "data")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "message_patterns.db")
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 创建模式表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    version TEXT DEFAULT '1.0.0',
                    category TEXT DEFAULT 'general',
                    tags TEXT,
                    author TEXT,
                    icon TEXT DEFAULT '📝',
                    data TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    favorite INTEGER DEFAULT 0,
                    is_system INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            # 创建使用记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage_records (
                    id TEXT PRIMARY KEY,
                    pattern_id TEXT NOT NULL,
                    pattern_name TEXT,
                    user_id TEXT,
                    input_content TEXT,
                    output_content TEXT,
                    variables TEXT,
                    quality_score REAL DEFAULT 0,
                    response_time REAL DEFAULT 0,
                    success INTEGER DEFAULT 1,
                    feedback TEXT,
                    created_at TEXT
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_category 
                ON patterns(category)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_name 
                ON patterns(name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_pattern 
                ON usage_records(pattern_id)
            """)

            conn.commit()
            conn.close()

    def _row_to_pattern(self, row: tuple) -> MessagePattern:
        """将数据库行转换为MessagePattern"""
        if not row:
            return None
        id_, name, desc, version, category, tags, author, icon, data, \
                enabled, favorite, is_system, created_at, updated_at = row
        pattern_dict = json.loads(data)
        pattern_dict["id"] = id_
        pattern_dict["name"] = name
        pattern_dict["description"] = desc
        pattern_dict["version"] = version
        pattern_dict["category"] = category
        pattern_dict["tags"] = json.loads(tags) if tags else []
        pattern_dict["author"] = author
        pattern_dict["icon"] = icon
        pattern_dict["enabled"] = bool(enabled)
        pattern_dict["favorite"] = bool(favorite)
        pattern_dict["is_system"] = bool(is_system)
        return MessagePattern.from_dict(pattern_dict)

    def save_pattern(self, pattern: MessagePattern) -> bool:
        """保存模式"""
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                now = datetime.now().isoformat()
                if not pattern.metadata.created_at:
                    pattern.metadata.created_at = now
                pattern.metadata.updated_at = now

                data = json.dumps(pattern.to_dict(), ensure_ascii=False)

                cursor.execute("""
                    INSERT OR REPLACE INTO patterns 
                    (id, name, description, version, category, tags, author, icon,
                     data, enabled, favorite, is_system, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pattern.id, pattern.name, pattern.description, pattern.version,
                    pattern.category.value if isinstance(pattern.category, PatternCategory) else pattern.category,
                    json.dumps(pattern.tags, ensure_ascii=False), pattern.author, pattern.icon,
                    data, int(pattern.enabled), int(pattern.favorite), int(pattern.is_system),
                    pattern.metadata.created_at, pattern.metadata.updated_at
                ))

                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error saving pattern: {e}")
                return False

    def get_pattern(self, pattern_id: str) -> Optional[MessagePattern]:
        """获取单个模式"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patterns WHERE id = ?", (pattern_id,))
            row = cursor.fetchone()
            conn.close()
            return self._row_to_pattern(row)

    def get_all_patterns(self, include_disabled: bool = False) -> List[MessagePattern]:
        """获取所有模式"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if include_disabled:
                cursor.execute("SELECT * FROM patterns ORDER BY updated_at DESC")
            else:
                cursor.execute("SELECT * FROM patterns WHERE enabled = 1 ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            conn.close()
            return [self._row_to_pattern(row) for row in rows]

    def get_patterns_by_category(self, category: PatternCategory) -> List[MessagePattern]:
        """按分类获取模式"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cat = category.value if isinstance(category, PatternCategory) else category
            cursor.execute(
                "SELECT * FROM patterns WHERE category = ? AND enabled = 1 ORDER BY updated_at DESC",
                (cat,)
            )
            rows = cursor.fetchall()
            conn.close()
            return [self._row_to_pattern(row) for row in rows]

    def get_favorite_patterns(self) -> List[MessagePattern]:
        """获取收藏的模式"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patterns WHERE favorite = 1 ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            conn.close()
            return [self._row_to_pattern(row) for row in rows]

    def search_patterns(self, query: str) -> List[MessagePattern]:
        """搜索模式"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            search = f"%{query}%"
            cursor.execute("""
                SELECT * FROM patterns 
                WHERE (name LIKE ? OR description LIKE ? OR tags LIKE ?)
                AND enabled = 1
                ORDER BY updated_at DESC
            """, (search, search, search))
            rows = cursor.fetchall()
            conn.close()
            return [self._row_to_pattern(row) for row in rows]

    def delete_pattern(self, pattern_id: str) -> bool:
        """删除模式"""
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM patterns WHERE id = ?", (pattern_id,))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error deleting pattern: {e}")
                return False

    def toggle_enabled(self, pattern_id: str, enabled: bool) -> bool:
        """切换启用状态"""
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE patterns SET enabled = ? WHERE id = ?", (int(enabled), pattern_id))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error toggling enabled: {e}")
                return False

    def toggle_favorite(self, pattern_id: str, favorite: bool) -> bool:
        """切换收藏状态"""
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE patterns SET favorite = ? WHERE id = ?", (int(favorite), pattern_id))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error toggling favorite: {e}")
                return False

    def save_usage_record(self, record: PatternUsageRecord) -> bool:
        """保存使用记录"""
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                if not record.created_at:
                    record.created_at = datetime.now().isoformat()

                cursor.execute("""
                    INSERT INTO usage_records 
                    (id, pattern_id, pattern_name, user_id, input_content, 
                     output_content, variables, quality_score, response_time,
                     success, feedback, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.id, record.pattern_id, record.pattern_name,
                    record.user_id, record.input_content, record.output_content,
                    json.dumps(record.variables, ensure_ascii=False),
                    record.quality_score, record.response_time,
                    int(record.success), record.feedback, record.created_at
                ))

                # 更新模式使用统计
                cursor.execute("""
                    UPDATE patterns 
                    SET metadata = json_set(metadata, '$.usage_count', 
                        COALESCE(json_extract(metadata, '$.usage_count'), 0) + 1)
                    WHERE id = ?
                """, (record.pattern_id,))

                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Error saving usage record: {e}")
                return False

    def get_usage_records(self, pattern_id: str, limit: int = 100) -> List[PatternUsageRecord]:
        """获取使用记录"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM usage_records 
                WHERE pattern_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (pattern_id, limit))
            rows = cursor.fetchall()
            conn.close()

            records = []
            for row in rows:
                id_, pattern_id, pattern_name, user_id, input_content, \
                    output_content, variables, quality_score, response_time, \
                    success, feedback, created_at = row
                records.append(PatternUsageRecord(
                    id=id_, pattern_id=pattern_id, pattern_name=pattern_name,
                    user_id=user_id, input_content=input_content,
                    output_content=output_content,
                    variables=json.loads(variables) if variables else {},
                    quality_score=quality_score, response_time=response_time,
                    success=bool(success), feedback=feedback, created_at=created_at
                ))
            return records

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 总模式数
            cursor.execute("SELECT COUNT(*) FROM patterns WHERE enabled = 1")
            total_patterns = cursor.fetchone()[0]

            # 分类统计
            cursor.execute("""
                SELECT category, COUNT(*) 
                FROM patterns WHERE enabled = 1 
                GROUP BY category
            """)
            category_stats = {row[0]: row[1] for row in cursor.fetchall()}

            # 使用统计
            cursor.execute("SELECT COUNT(*) FROM usage_records")
            total_usage = cursor.fetchone()[0]

            cursor.execute("""
                SELECT AVG(quality_score), AVG(response_time) 
                FROM usage_records WHERE quality_score > 0
            """)
            avg_score, avg_time = cursor.fetchone()

            conn.close()

            return {
                "total_patterns": total_patterns,
                "category_stats": category_stats,
                "total_usage": total_usage,
                "avg_quality_score": avg_score or 0.0,
                "avg_response_time": avg_time or 0.0
            }


class PatternManager:
    """消息模式管理器 - 核心管理器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = None):
        if not hasattr(self, "_initialized"):
            self._db = PatternDatabase(db_path)
            self._observers: List[Callable] = []
            self._initialized = True
            self._init_builtin_patterns()

    def _init_builtin_patterns(self):
        """初始化内置模式"""
        builtin = BuiltInPatterns.get_all_builtin_patterns()
        for pattern in builtin:
            existing = self._db.get_pattern(pattern.id)
            if not existing:
                self._db.save_pattern(pattern)

    def _notify_observers(self, event: str, data: Any = None):
        """通知观察者"""
        for observer in self._observers:
            try:
                observer(event, data)
            except Exception as e:
                print(f"Observer error: {e}")

    def add_observer(self, observer: Callable):
        """添加观察者"""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: Callable):
        """移除观察者"""
        if observer in self._observers:
            self._observers.remove(observer)

    # ============ CRUD 操作 ============

    def create_pattern(self, pattern: MessagePattern) -> bool:
        """创建模式"""
        result = self._db.save_pattern(pattern)
        if result:
            self._notify_observers("pattern_created", pattern)
        return result

    def get_pattern(self, pattern_id: str) -> Optional[MessagePattern]:
        """获取模式"""
        return self._db.get_pattern(pattern_id)

    def get_all_patterns(self, include_disabled: bool = False) -> List[MessagePattern]:
        """获取所有模式"""
        return self._db.get_all_patterns(include_disabled)

    def update_pattern(self, pattern: MessagePattern) -> bool:
        """更新模式"""
        result = self._db.save_pattern(pattern)
        if result:
            self._notify_observers("pattern_updated", pattern)
        return result

    def delete_pattern(self, pattern_id: str) -> bool:
        """删除模式"""
        pattern = self._db.get_pattern(pattern_id)
        if pattern and pattern.is_system:
            return False  # 不能删除系统内置模式
        result = self._db.delete_pattern(pattern_id)
        if result:
            self._notify_observers("pattern_deleted", pattern_id)
        return result

    def toggle_enabled(self, pattern_id: str, enabled: bool) -> bool:
        """切换启用状态"""
        result = self._db.toggle_enabled(pattern_id, enabled)
        if result:
            self._notify_observers("pattern_toggled", {"id": pattern_id, "enabled": enabled})
        return result

    def toggle_favorite(self, pattern_id: str, favorite: bool) -> bool:
        """切换收藏状态"""
        result = self._db.toggle_favorite(pattern_id, favorite)
        if result:
            self._notify_observers("pattern_favorited", {"id": pattern_id, "favorite": favorite})
        return result

    # ============ 查询操作 ============

    def get_by_category(self, category: PatternCategory) -> List[MessagePattern]:
        """按分类获取"""
        return self._db.get_patterns_by_category(category)

    def get_favorites(self) -> List[MessagePattern]:
        """获取收藏"""
        return self._db.get_favorite_patterns()

    def search(self, query: str) -> List[MessagePattern]:
        """搜索模式"""
        return self._db.search_patterns(query)

    def get_recent(self, limit: int = 10) -> List[MessagePattern]:
        """获取最近使用的模式"""
        patterns = self._db.get_all_patterns()
        sorted_patterns = sorted(
            patterns,
            key=lambda p: p.metadata.last_used or "",
            reverse=True
        )
        return sorted_patterns[:limit]

    def get_most_used(self, limit: int = 10) -> List[MessagePattern]:
        """获取最常用的模式"""
        patterns = self._db.get_all_patterns()
        sorted_patterns = sorted(
            patterns,
            key=lambda p: p.metadata.usage_count,
            reverse=True
        )
        return sorted_patterns[:limit]

    def get_system_patterns(self) -> List[MessagePattern]:
        """获取系统内置模式"""
        patterns = self._db.get_all_patterns()
        return [p for p in patterns if p.is_system]

    def get_user_patterns(self) -> List[MessagePattern]:
        """获取用户自定义模式"""
        patterns = self._db.get_all_patterns()
        return [p for p in patterns if not p.is_system]

    # ============ 导入导出 ============

    def export_pattern(self, pattern_id: str, file_path: str = None) -> Optional[str]:
        """导出单个模式"""
        pattern = self._db.get_pattern(pattern_id)
        if not pattern:
            return None

        if file_path is None:
            export_dir = os.path.join(os.path.expanduser("~"), ".hermes-desktop", "exports")
            os.makedirs(export_dir, exist_ok=True)
            file_path = os.path.join(export_dir, f"{pattern.name}_{pattern.id[:8]}.mp.json")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(pattern.to_json())

        return file_path

    def export_all(self, file_path: str = None) -> str:
        """导出所有用户模式"""
        if file_path is None:
            export_dir = os.path.join(os.path.expanduser("~"), ".hermes-desktop", "exports")
            os.makedirs(export_dir, exist_ok=True)
            file_path = os.path.join(export_dir, f"all_patterns_{datetime.now().strftime('%Y%m%d')}.mp.json")

        patterns = self.get_user_patterns()
        data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "count": len(patterns),
            "patterns": [p.to_dict() for p in patterns]
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return file_path

    def import_pattern(self, file_path: str) -> Optional[MessagePattern]:
        """导入单个模式"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 判断是单个模式还是批量导出
            if content.strip().startswith("{"):
                data = json.loads(content)
                if "patterns" in data:
                    # 批量导出
                    for p_data in data["patterns"]:
                        pattern = MessagePattern.from_dict(p_data)
                        # 生成新ID避免冲突
                        import uuid
                        pattern.id = str(uuid.uuid4())
                        pattern.is_system = False
                        self._db.save_pattern(pattern)
                    return None
                else:
                    # 单个模式
                    pattern = MessagePattern.from_dict(data)
        except Exception as e:
            print(f"Import error: {e}")
            return None

        return pattern

    def import_from_url(self, url: str) -> Optional[MessagePattern]:
        """从URL导入模式"""
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                pattern = MessagePattern.from_dict(data)
                return pattern
        except Exception as e:
            print(f"URL import error: {e}")
            return None

    # ============ 使用统计 ============

    def record_usage(self, record: PatternUsageRecord) -> bool:
        """记录使用"""
        return self._db.save_usage_record(record)

    def get_usage_records(self, pattern_id: str, limit: int = 100) -> List[PatternUsageRecord]:
        """获取使用记录"""
        return self._db.get_usage_records(pattern_id, limit)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._db.get_statistics()

    # ============ 批量操作 ============

    def duplicate_pattern(self, pattern_id: str, new_name: str = None) -> Optional[MessagePattern]:
        """复制模式"""
        original = self._db.get_pattern(pattern_id)
        if not original:
            return None

        import uuid
        new_pattern = MessagePattern.from_dict(original.to_dict())
        new_pattern.id = str(uuid.uuid4())
        new_pattern.name = new_name or f"{original.name} (副本)"
        new_pattern.metadata = PatternMetadata()
        new_pattern.is_system = False
        new_pattern.sharing.public = False

        if self._db.save_pattern(new_pattern):
            return new_pattern
        return None

    def merge_patterns(self, pattern_ids: List[str], new_name: str) -> Optional[MessagePattern]:
        """合并多个模式"""
        patterns = [self._db.get_pattern(pid) for pid in pattern_ids]
        patterns = [p for p in patterns if p]

        if not patterns:
            return None

        # 创建新模式，合并模板
        new_pattern = MessagePattern()
        import uuid
        new_pattern.id = str(uuid.uuid4())
        new_pattern.name = new_name

        # 简单合并：拼接模板内容
        combined_content = "\n\n---\n\n".join([p.template.content for p in patterns])
        new_pattern.template.content = combined_content

        # 合并变量
        for p in patterns:
            for k, v in p.template.variables.items():
                if k not in new_pattern.template.variables:
                    new_pattern.template.variables[k] = v

        # 合并标签
        all_tags = set()
        for p in patterns:
            all_tags.update(p.tags)
        new_pattern.tags = list(all_tags)

        if self._db.save_pattern(new_pattern):
            return new_pattern
        return None

    # ============ 模板创建 ============

    def create_from_template(
        self,
        name: str,
        description: str,
        template_content: str,
        category: PatternCategory = PatternCategory.GENERAL,
        variables: Dict[str, Any] = None,
        keywords: List[str] = None
    ) -> MessagePattern:
        """从模板创建模式"""
        pattern = MessagePattern()
        pattern.name = name
        pattern.description = description
        pattern.category = category
        pattern.template.content = template_content
        pattern.template.variables = variables or {}

        if keywords:
            pattern.trigger.type = TriggerType.KEYWORD
            pattern.trigger.keywords = keywords

        self._db.save_pattern(pattern)
        return pattern


# 全局实例
_manager_instance = None


def get_pattern_manager() -> PatternManager:
    """获取模式管理器实例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = PatternManager()
    return _manager_instance
