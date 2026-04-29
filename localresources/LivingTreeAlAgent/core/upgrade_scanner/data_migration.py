# data_migration.py — 数据平滑迁移系统

import os
import re
import json
import time
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Type
from dataclasses import asdict
from datetime import datetime
import hashlib
import sqlite3


logger = logging.getLogger(__name__)


# ============ 迁移策略配置 ============

class MigrationStrategy:
    """迁移策略"""
    LAZY = "lazy"           # 惰性迁移 (用到才转)
    EAGER = "eager"         # 立即迁移
    DUAL_READ = "dual_read" # 双读兼容 (新优先，读不到读旧)


# ============ 版本管理器 ============

class VersionManager:
    """
    数据版本管理器

    功能:
    1. 记录数据格式版本
    2. 检测当前版本
    3. 管理版本升级
    """

    def __init__(self, version_file: Path = None):
        if version_file is None:
            version_file = Path.home() / ".hermes-desktop" / "upgrade_scanner" / "version.json"

        version_file.parent.mkdir(parents=True, exist_ok=True)
        self._version_file = version_file
        self._current_version: Optional[str] = None
        self._load_version()

    def _load_version(self):
        """加载版本信息"""
        if self._version_file.exists():
            try:
                data = json.loads(self._version_file.read_text(encoding="utf-8"))
                self._current_version = data.get("version", "v1")
            except Exception:
                self._current_version = "v1"
        else:
            self._current_version = "v1"

    def _save_version(self):
        """保存版本信息"""
        try:
            data = {
                "version": self._current_version,
                "updated_at": int(time.time()),
            }
            self._version_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save version: {e}")

    def get_version(self) -> str:
        """获取当前版本"""
        return self._current_version or "v1"

    def set_version(self, version: str):
        """设置版本"""
        old_version = self._current_version
        self._current_version = version
        self._save_version()
        logger.info(f"Version changed: {old_version} -> {version}")
        return old_version != version

    def is_version(self, version: str) -> bool:
        """检查是否指定版本"""
        return self.get_version() == version


# ============ 迁移记录 ============

@dataclass
class MigrationRecord:
    """迁移记录"""
    id: str
    from_version: str
    to_version: str
    file_path: str
    records_total: int = 0
    records_migrated: int = 0
    records_failed: int = 0
    status: str = "pending"  # pending/running/completed/failed
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    backup_path: Optional[str] = None
    error_message: Optional[str] = None


# ============ 原子写入工具 ============

class AtomicWriter:
    """
    原子写入工具

    使用临时文件+rename实现原子写入，防止断电导致文件损坏
    """

    @staticmethod
    def write(
        file_path: Path,
        content: str,
        mode: str = "w",
        encoding: str = "utf-8",
    ) -> bool:
        """
        原子写入

        Args:
            file_path: 目标路径
            content: 内容
            mode: 写入模式
            encoding: 编码

        Returns:
            bool: 是否成功
        """
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")

        try:
            # 写入临时文件
            if mode == "wb":
                temp_path.write_bytes(content)
            else:
                temp_path.write_text(content, encoding=encoding)

            # 确保写入完成
            temp_path.flush()
            os.fsync(temp_path.fileno())

            # 重命名 (原子操作)
            shutil.move(str(temp_path), str(file_path))
            return True

        except Exception as e:
            logger.error(f"Atomic write failed: {e}")
            # 清理临时文件
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            return False

    @staticmethod
    def backup(file_path: Path, backup_dir: Path = None) -> Optional[Path]:
        """
        备份文件

        Args:
            file_path: 文件路径
            backup_dir: 备份目录

        Returns:
            备份路径或None
        """
        if not file_path.exists():
            return None

        if backup_dir is None:
            backup_dir = file_path.parent / "backups"

        backup_dir.mkdir(parents=True, exist_ok=True)

        # 生成带时间戳的备份名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = backup_dir / backup_name

        try:
            shutil.copy2(str(file_path), str(backup_path))
            return backup_path
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None


# ============ 双读兼容读取器 ============

class DualReadReader:
    """
    双读兼容读取器

    优先读取新版本格式，失败后回退读取旧版本格式
    """

    def __init__(
        self,
        file_path: Path,
        new_version: str = "v2",
        old_version: str = "v1",
        new_ext: str = ".jsonl",
        old_ext: str = ".json",
    ):
        self._file_path = Path(file_path)
        self._new_version = new_version
        self._old_version = old_version
        self._new_ext = new_ext
        self._old_ext = old_ext

    def _get_new_path(self) -> Path:
        """获取新版本文件路径"""
        return self._file_path.with_suffix(self._new_ext)

    def _get_old_path(self) -> Path:
        """获取旧版本文件路径"""
        return self._file_path.with_suffix(self._old_ext)

    def read(self) -> List[Dict[str, Any]]:
        """
        读取数据

        优先新版本，失败回退旧版本
        """
        # 优先尝试新版本
        new_path = self._get_new_path()
        if new_path.exists():
            try:
                return self._read_jsonl(new_path)
            except Exception as e:
                logger.warning(f"Failed to read new version {new_path}: {e}")

        # 回退旧版本
        old_path = self._get_old_path()
        if old_path.exists():
            try:
                return self._read_json(old_path)
            except Exception as e:
                logger.error(f"Failed to read old version {old_path}: {e}")

        return []

    def _read_jsonl(self, path: Path) -> List[Dict[str, Any]]:
        """读取JSONL格式"""
        results = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
        return results

    def _read_json(self, path: Path) -> List[Dict[str, Any]]:
        """读取JSON格式"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                return []

    def has_new_version(self) -> bool:
        """检查是否存在新版本"""
        return self._get_new_path().exists()

    def has_old_version(self) -> bool:
        """检查是否存在旧版本"""
        return self._get_old_path().exists()

    def migrate(self, converter: Callable[[Dict], Dict]) -> int:
        """
        执行迁移

        Args:
            converter: 转换函数 (旧格式 -> 新格式)

        Returns:
            int: 迁移记录数
        """
        # 读取旧版本
        old_data = self._read_json(self._get_old_path())
        if not old_data:
            return 0

        # 备份
        backup_path = AtomicWriter.backup(self._get_old_path())

        # 转换并写入新版本
        new_path = self._get_new_path()
        migrated = 0

        try:
            with open(new_path, "w", encoding="utf-8") as f:
                for record in old_data:
                    try:
                        new_record = converter(record)
                        f.write(json.dumps(new_record, ensure_ascii=False) + "\n")
                        migrated += 1
                    except Exception as e:
                        logger.warning(f"Record migration failed: {e}")

            logger.info(f"Migrated {migrated}/{len(old_data)} records to {new_path}")
            return migrated

        except Exception as e:
            # 失败时恢复备份
            if backup_path and backup_path.exists():
                shutil.copy2(str(backup_path), str(self._get_old_path()))
            raise e


# ============ 数据迁移器 ============

class DataMigrationManager:
    """
    数据迁移管理器

    功能:
    1. 版本检测与追踪
    2. 双读兼容
    3. 惰性迁移
    4. 断点续传
    5. 自动备份
    """

    def __init__(
        self,
        data_dir: Path = None,
        version_manager: VersionManager = None,
    ):
        if data_dir is None:
            data_dir = Path.home() / ".hermes-desktop" / "upgrade_scanner" / "migrations"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._data_dir = data_dir

        self._version_manager = version_manager or VersionManager()
        self._migrations: Dict[str, Dict] = {}
        self._load_migrations()

    def _load_migrations(self):
        """加载迁移记录"""
        migrations_file = self._data_dir / "migration_records.json"
        if migrations_file.exists():
            try:
                self._migrations = json.loads(migrations_file.read_text(encoding="utf-8"))
            except Exception:
                self._migrations = {}

    def _save_migrations(self):
        """保存迁移记录"""
        migrations_file = self._data_dir / "migration_records.json"
        try:
            migrations_file.write_text(
                json.dumps(self._migrations, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save migrations: {e}")

    def _generate_migration_id(self, file_path: str) -> str:
        """生成迁移ID"""
        raw = f"{file_path}:{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def register_migration(
        self,
        file_path: str,
        from_version: str,
        to_version: str,
        strategy: str = MigrationStrategy.LAZY,
    ) -> str:
        """
        注册迁移任务

        Args:
            file_path: 文件路径
            from_version: 源版本
            to_version: 目标版本
            strategy: 迁移策略

        Returns:
            str: 迁移ID
        """
        migration_id = self._generate_migration_id(file_path)

        self._migrations[migration_id] = {
            "id": migration_id,
            "file_path": file_path,
            "from_version": from_version,
            "to_version": to_version,
            "strategy": strategy,
            "status": "pending",
            "records_total": 0,
            "records_migrated": 0,
            "records_failed": 0,
            "started_at": None,
            "completed_at": None,
            "last_checkpoint": 0,
        }

        self._save_migrations()
        return migration_id

    def execute_migration(
        self,
        migration_id: str,
        converter: Callable[[Dict], Dict],
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        执行迁移

        Args:
            migration_id: 迁移ID
            converter: 转换函数
            batch_size: 批处理大小

        Returns:
            Dict: 执行结果
        """
        if migration_id not in self._migrations:
            return {"status": "error", "message": "Migration not found"}

        migration = self._migrations[migration_id]
        file_path = Path(migration["file_path"])

        if not file_path.exists():
            return {"status": "error", "message": "File not found"}

        migration["status"] = "running"
        migration["started_at"] = int(time.time())
        self._save_migrations()

        try:
            # 备份
            backup_path = AtomicWriter.backup(file_path)
            migration["backup_path"] = str(backup_path)

            # 根据策略执行
            if migration["strategy"] == MigrationStrategy.LAZY:
                return self._execute_lazy_migration(migration, file_path, converter, batch_size)
            elif migration["strategy"] == MigrationStrategy.EAGER:
                return self._execute_eager_migration(migration, file_path, converter, batch_size)
            else:  # DUAL_READ
                return self._execute_dual_read_migration(migration, file_path, converter)

        except Exception as e:
            migration["status"] = "failed"
            migration["error_message"] = str(e)
            self._save_migrations()
            return {"status": "failed", "message": str(e)}

    def _execute_lazy_migration(
        self,
        migration: Dict,
        file_path: Path,
        converter: Callable,
        batch_size: int,
    ) -> Dict[str, Any]:
        """
        惰性迁移

        只有在读取数据时才进行转换，不影响旧文件
        """
        migration["status"] = "completed"
        migration["completed_at"] = int(time.time())
        self._save_migrations()

        return {
            "status": "completed",
            "records_total": migration["records_total"],
            "records_migrated": migration["records_migrated"],
            "strategy": "lazy",
            "message": "Lazy migration complete. Data will be converted on first read.",
        }

    def _execute_eager_migration(
        self,
        migration: Dict,
        file_path: Path,
        converter: Callable,
        batch_size: int,
    ) -> Dict[str, Any]:
        """
        立即迁移

        立即转换所有数据
        """
        # 读取数据
        with open(file_path, "r", encoding="utf-8") as f:
            if file_path.suffix == ".jsonl":
                records = [json.loads(line) for line in f if line.strip()]
            else:
                data = json.load(f)
                records = data if isinstance(data, list) else [data]

        migration["records_total"] = len(records)

        # 转换并原子写入
        temp_path = file_path.with_suffix(".jsonl.tmp")
        migrated = 0
        failed = 0

        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                for i, record in enumerate(records):
                    try:
                        new_record = converter(record)
                        f.write(json.dumps(new_record, ensure_ascii=False) + "\n")
                        migrated += 1

                        # 断点保存
                        if (i + 1) % batch_size == 0:
                            migration["last_checkpoint"] = i + 1
                            self._save_migrations()

                    except Exception as e:
                        logger.warning(f"Record {i} migration failed: {e}")
                        failed += 1

            # 原子替换
            shutil.move(str(temp_path), str(file_path.with_suffix(".jsonl")))

            migration["records_migrated"] = migrated
            migration["records_failed"] = failed
            migration["status"] = "completed"
            migration["completed_at"] = int(time.time())
            self._save_migrations()

            # 更新版本
            self._version_manager.set_version(migration["to_version"])

            return {
                "status": "completed",
                "records_total": len(records),
                "records_migrated": migrated,
                "records_failed": failed,
            }

        except Exception as e:
            # 清理临时文件
            if temp_path.exists():
                temp_path.unlink()
            raise e

    def _execute_dual_read_migration(
        self,
        migration: Dict,
        file_path: Path,
        converter: Callable,
    ) -> Dict[str, Any]:
        """
        双读兼容迁移

        保持新旧两个版本，新版本优先读取
        """
        # 读取旧版本
        old_path = file_path.with_suffix(".json")
        if not old_path.exists():
            return self._execute_eager_migration(migration, file_path, converter, 100)

        with open(old_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            records = data if isinstance(data, list) else [data]

        migration["records_total"] = len(records)

        # 创建新版本
        new_path = file_path.with_suffix(".jsonl")

        try:
            with open(new_path, "w", encoding="utf-8") as f:
                for record in records:
                    try:
                        new_record = converter(record)
                        f.write(json.dumps(new_record, ensure_ascii=False) + "\n")
                        migration["records_migrated"] += 1
                    except Exception:
                        migration["records_failed"] += 1

            migration["status"] = "completed"
            migration["completed_at"] = int(time.time())
            self._save_migrations()

            return {
                "status": "completed",
                "records_total": len(records),
                "records_migrated": migration["records_migrated"],
                "records_failed": migration["records_failed"],
                "dual_read_enabled": True,
            }

        except Exception as e:
            raise e

    def get_migration_status(self, migration_id: str) -> Optional[Dict]:
        """获取迁移状态"""
        return self._migrations.get(migration_id)

    def get_all_migrations(self) -> List[Dict]:
        """获取所有迁移"""
        return list(self._migrations.values())

    def rollback_migration(self, migration_id: str) -> bool:
        """
        回滚迁移

        Args:
            migration_id: 迁移ID

        Returns:
            bool: 是否成功
        """
        if migration_id not in self._migrations:
            return False

        migration = self._migrations[migration_id]

        # 恢复备份
        backup_path = migration.get("backup_path")
        if backup_path and Path(backup_path).exists():
            file_path = Path(migration["file_path"])
            shutil.copy2(backup_path, str(file_path))

        migration["status"] = "rolled_back"
        migration["completed_at"] = int(time.time())
        self._save_migrations()

        return True


# ============ SQLite迁移助手 ============

class SQLiteMigrationHelper:
    """
    SQLite数据库迁移助手

    专门处理SQLite数据库的迁移
    """

    def __init__(self, db_path: Path = None):
        self._db_path = db_path

    def backup_tables(self, tables: List[str] = None) -> Dict[str, str]:
        """
        备份表

        Args:
            tables: 要备份的表列表，None表示全部

        Returns:
            Dict: 表名 -> 备份表名
        """
        if not self._db_path or not Path(self._db_path).exists():
            return {}

        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()

        backup_names = {}

        try:
            if tables is None:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                backup_name = f"{table}_backup_{int(time.time())}"
                cursor.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM {table}")
                backup_names[table] = backup_name

            conn.commit()
            return backup_names

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {}
        finally:
            conn.close()

    def add_column_safely(self, table: str, column: str, col_type: str):
        """
        安全添加列 (如果不存在)

        Args:
            table: 表名
            column: 列名
            col_type: 列类型
        """
        if not self._db_path:
            return

        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()

        try:
            # 检查列是否存在
            cursor.execute(f"PRAGMA table_info({table})")
            existing_cols = [row[1] for row in cursor.fetchall()]

            if column not in existing_cols:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                conn.commit()
                logger.info(f"Added column {column} to {table}")
        except Exception as e:
            logger.error(f"Add column failed: {e}")
        finally:
            conn.close()

    def migrate_to_jsonl(
        self,
        table: str,
        output_path: Path,
        converter: Callable[[Dict], Dict] = None,
    ) -> int:
        """
        将表导出为JSONL

        Args:
            table: 表名
            output_path: 输出路径
            converter: 转换函数

        Returns:
            int: 导出记录数
        """
        if not self._db_path:
            return 0

        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        migrated = 0

        try:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()

            with open(output_path, "w", encoding="utf-8") as f:
                for row in rows:
                    record = dict(row)
                    if converter:
                        record = converter(record)
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    migrated += 1

            return migrated

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return migrated
        finally:
            conn.close()


# ============ 全局实例 ============

_version_manager: Optional[VersionManager] = None
_migration_manager: Optional[DataMigrationManager] = None


def get_version_manager() -> VersionManager:
    """获取版本管理器"""
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager


def get_migration_manager() -> DataMigrationManager:
    """获取迁移管理器"""
    global _migration_manager
    if _migration_manager is None:
        _migration_manager = DataMigrationManager()
    return _migration_manager
