"""
GBrain 同步管理
支持与 Git 仓库同步、导入/导出

灵感来源：GBrain 使用 Git Markdown 仓库作为"真相之源"
"""

import json
import time
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from core.gbrain_memory.page_manager import PageManager


class SyncStatus(Enum):
    """同步状态"""
    IDLE = "idle"
    SYNCING = "syncing"
    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"


class ConflictResolution(Enum):
    """冲突解决策略"""
    KEEP_LOCAL = "keep_local"
    KEEP_REMOTE = "keep_remote"
    KEEP_BOTH = "keep_both"
    MANUAL = "manual"


@dataclass
class SyncResult:
    """同步结果"""
    status: SyncStatus
    message: str
    pages_added: int = 0
    pages_updated: int = 0
    pages_conflicted: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class GitRepo:
    """Git 仓库信息"""
    path: str
    remote_url: str = ""
    branch: str = "main"
    last_sync: float = 0


class SyncManager:
    """
    同步管理器

    功能：
    1. 与 Git 仓库同步（push/pull）
    2. 导入/导出 Markdown 文件
    3. 冲突检测和解决
    4. 备份管理
    """

    def __init__(self, brain_dir: str | Path = None):
        from client.src.business.config import get_config_dir

        if brain_dir is None:
            brain_dir = get_config_dir() / "gbrain"

        self.brain_dir = Path(brain_dir)
        self.pages_dir = self.brain_dir / "pages"
        self.backup_dir = self.brain_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)

        self.page_manager = PageManager(brain_dir)

        # Git 仓库信息
        self.git_repo: Optional[GitRepo] = None
        self._detect_git_repo()

        # 同步配置
        self.config = {
            "auto_sync": False,  # 自动同步
            "sync_interval": 3600,  # 同步间隔（秒）
            "backup_before_sync": True,  # 同步前备份
            "conflict_resolution": ConflictResolution.KEEP_BOTH.value,
        }

    def _detect_git_repo(self):
        """检测 Git 仓库"""
        if not self.brain_dir.exists():
            return

        # 检查是否有 .git 目录
        git_dir = self.brain_dir / ".git"
        if not git_dir.exists():
            return

        try:
            # 获取远程 URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=str(self.brain_dir),
                capture_output=True,
                text=True
            )
            remote_url = result.stdout.strip() if result.returncode == 0 else ""

            # 获取当前分支
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(self.brain_dir),
                capture_output=True,
                text=True
            )
            branch = result.stdout.strip() if result.returncode == 0 else "main"

            self.git_repo = GitRepo(
                path=str(self.brain_dir),
                remote_url=remote_url,
                branch=branch
            )
        except Exception:
            pass

    def init_git_repo(self, remote_url: str = None) -> bool:
        """
        初始化 Git 仓库

        Args:
            remote_url: 可选的远程仓库 URL

        Returns:
            是否成功
        """
        try:
            # 初始化仓库
            subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=str(self.brain_dir),
                check=True,
                capture_output=True
            )

            # 添加远程
            if remote_url:
                subprocess.run(
                    ["git", "remote", "add", "origin", remote_url],
                    cwd=str(self.brain_dir),
                    check=True,
                    capture_output=True
                )

            # 创建 .gitignore
            gitignore = self.brain_dir / ".gitignore"
            gitignore.write_text("""
# 忽略数据库和缓存
*.db
*.db-journal
__pycache__/
*.pyc

# 忽略备份
backups/

# 忽略 IDE 配置
.vscode/
.idea/
*.swp
*.swo
""", encoding="utf-8")

            # 初始提交
            subprocess.run(
                ["git", "add", "."],
                cwd=str(self.brain_dir),
                check=True,
                capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit: GBrain memory repository"],
                cwd=str(self.brain_dir),
                check=True,
                capture_output=True
            )

            self._detect_git_repo()
            return True

        except Exception:
            return False

    def sync(
        self,
        direction: str = "pull",  # "pull" | "push" | "both"
        resolution: ConflictResolution = None
    ) -> SyncResult:
        """
        同步记忆

        Args:
            direction: 同步方向
            resolution: 冲突解决策略

        Returns:
            SyncResult
        """
        if not self.git_repo:
            return SyncResult(
                status=SyncStatus.FAILED,
                message="未检测到 Git 仓库，请先调用 init_git_repo"
            )

        if resolution is None:
            resolution = ConflictResolution(self.config["conflict_resolution"])

        # 同步前备份
        if self.config["backup_before_sync"]:
            self._create_backup("pre_sync")

        result = SyncResult(status=SyncStatus.SYNCING, message="同步中...")

        try:
            if direction in ["pull", "both"]:
                pull_result = self._git_pull(resolution)
                result.pages_updated += pull_result.get("updated", 0)
                result.pages_conflicted += pull_result.get("conflicted", 0)

            if direction in ["push", "both"]:
                push_result = self._git_push()
                result.pages_added += push_result.get("added", 0)
                result.pages_updated += push_result.get("updated", 0)

            # 更新最后同步时间
            if self.git_repo:
                self.git_repo.last_sync = time.time()

            result.status = SyncStatus.SUCCESS
            result.message = f"同步完成：新增{result.pages_added}，更新{result.pages_updated}，冲突{result.pages_conflicted}"

        except Exception as e:
            result.status = SyncStatus.FAILED
            result.message = f"同步失败：{str(e)}"
            result.errors.append(str(e))

        return result

    def _git_pull(self, resolution: ConflictResolution) -> Dict[str, int]:
        """Git Pull"""
        try:
            # 先 fetch
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=str(self.brain_dir),
                check=True,
                capture_output=True
            )

            # 尝试合并
            result = subprocess.run(
                ["git", "pull", "origin", self.git_repo.branch, "--no-edit"],
                cwd=str(self.brain_dir),
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # 重新加载页面
                self._reload_pages()
                return {"updated": 1}

            # 有冲突
            if "CONFLICT" in result.stderr or result.returncode != 0:
                return self._handle_conflicts(resolution)

            return {"updated": 0}

        except Exception as e:
            return {"updated": 0, "errors": [str(e)]}

    def _git_push(self) -> Dict[str, int]:
        """Git Push"""
        try:
            # 添加所有更改
            subprocess.run(
                ["git", "add", "."],
                cwd=str(self.brain_dir),
                check=True,
                capture_output=True
            )

            # 检查是否有更改
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.brain_dir),
                capture_output=True,
                text=True
            )

            if not result.stdout.strip():
                return {"added": 0, "updated": 0}

            # 提交
            commit_msg = f"GBrain sync: {time.strftime('%Y-%m-%d %H:%M')}"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=str(self.brain_dir),
                check=True,
                capture_output=True
            )

            # 推送
            subprocess.run(
                ["git", "push", "origin", self.git_repo.branch],
                cwd=str(self.brain_dir),
                check=True,
                capture_output=True
            )

            return {"added": 1, "updated": 0}

        except Exception as e:
            return {"added": 0, "updated": 0, "errors": [str(e)]}

    def _handle_conflicts(self, resolution: ConflictResolution) -> Dict[str, int]:
        """处理冲突"""
        conflicted_files = list(self.brain_dir.glob("**/*.md.CONFLICT"))

        for conflict_file in conflicted_files:
            if resolution == ConflictResolution.KEEP_LOCAL:
                # 保留本地版本，删除冲突文件
                original = conflict_file.with_suffix("")
                if original.exists():
                    original.unlink()
                conflict_file.rename(original)

            elif resolution == ConflictResolution.KEEP_REMOTE:
                # 保留远程版本
                original = conflict_file.with_suffix("")
                conflict_file.rename(original)

            elif resolution == ConflictResolution.KEEP_BOTH:
                # 保留两个版本（重命名）
                local_name = conflict_file.with_name(
                    conflict_file.stem.replace(".CONFLICT", "_local") + ".md"
                )
                conflict_file.rename(local_name)

        return {"conflicted": len(conflicted_files)}

    def _reload_pages(self):
        """重新加载所有页面"""
        # 清空并重新索引
        # TODO: 实现增量重载
        pass

    # === 导入/导出 ===

    def export_all(self, format: str = "markdown", output_dir: str = None) -> str:
        """
        导出所有记忆

        Args:
            format: 导出格式（markdown/json）
            output_dir: 输出目录

        Returns:
            导出文件路径
        """
        if output_dir is None:
            output_dir = self.brain_dir / "exports"
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        if format == "json":
            # 导出为单个 JSON 文件
            pages = self.page_manager.get_all_pages(limit=10000)
            data = {
                "export_time": time.time(),
                "export_time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_pages": len(pages),
                "pages": [p.to_dict() for p in pages]
            }

            output_file = output_dir / f"gbrain_export_{int(time.time())}.json"
            output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(output_file)

        else:
            # 导出为 Markdown 文件（每个页面一个文件）
            export_pages_dir = output_dir / "gbrain_pages"
            export_pages_dir.mkdir(parents=True, exist_ok=True)

            pages = self.page_manager.get_all_pages(limit=10000)
            for page in pages:
                output_file = export_pages_dir / f"{page.id}.md"
                output_file.write_text(page.to_markdown(), encoding="utf-8")

            # 导出索引
            index_file = output_dir / "gbrain_index.json"
            index_data = {
                "export_time": time.time(),
                "total_pages": len(pages),
                "pages": [{"id": p.id, "title": p.title, "category": p.category.value} for p in pages]
            }
            index_file.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")

            return str(export_pages_dir)

    def import_from_dir(self, import_dir: str | Path, merge: bool = True) -> SyncResult:
        """
        从目录导入记忆

        Args:
            import_dir: 导入目录
            merge: 是否合并（True=合并，False=覆盖）

        Returns:
            导入结果
        """
        import_dir = Path(import_dir)
        result = SyncResult(status=SyncStatus.SYNCING, message="导入中...")

        if not import_dir.exists():
            result.status = SyncStatus.FAILED
            result.message = f"导入目录不存在：{import_dir}"
            return result

        try:
            md_files = list(import_dir.glob("**/*.md"))
            imported = 0
            skipped = 0

            for md_file in md_files:
                content = md_file.read_text(encoding="utf-8")

                # 解析页面
                from core.gbrain_memory.models import BrainPage
                page = BrainPage.from_markdown(content)

                # 检查是否已存在
                existing = self.page_manager.get_page(page.id)
                if existing and merge:
                    # 合并
                    self.page_manager.merge_pages(page.id, existing.id, delete_source=True)
                    result.pages_updated += 1
                elif existing:
                    skipped += 1
                    continue
                else:
                    # 新建
                    self.page_manager._save_page(page)
                    imported += 1

            result.pages_added = imported
            result.status = SyncStatus.SUCCESS
            result.message = f"导入完成：新增{imported}，更新{result.pages_updated}，跳过{skipped}"

        except Exception as e:
            result.status = SyncStatus.FAILED
            result.message = f"导入失败：{str(e)}"
            result.errors.append(str(e))

        return result

    # === 备份管理 ===

    def _create_backup(self, tag: str = None) -> str:
        """创建备份"""
        if tag is None:
            tag = time.strftime("%Y%m%d_%H%M%S")

        backup_dir = self.backup_dir / f"backup_{tag}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # 复制所有页面
        if self.pages_dir.exists():
            for page_file in self.pages_dir.glob("*.md"):
                shutil.copy2(page_file, backup_dir / page_file.name)

        # 复制数据库
        db_path = self.brain_dir / "gbrain.db"
        if db_path.exists():
            shutil.copy2(db_path, backup_dir / "gbrain.db")

        return str(backup_dir)

    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份"""
        if not self.backup_dir.exists():
            return []

        backups = []
        for backup_dir in self.backup_dir.iterdir():
            if backup_dir.is_dir():
                stat = backup_dir.stat()
                backups.append({
                    "name": backup_dir.name,
                    "path": str(backup_dir),
                    "created": stat.st_mtime,
                    "created_str": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
                    "page_count": len(list(backup_dir.glob("*.md")))
                })

        return sorted(backups, key=lambda x: x["created"], reverse=True)

    def restore_backup(self, backup_name: str) -> bool:
        """
        恢复备份

        Args:
            backup_name: 备份目录名

        Returns:
            是否成功
        """
        backup_dir = self.backup_dir / backup_name
        if not backup_dir.exists():
            return False

        try:
            # 先备份当前状态
            self._create_backup("pre_restore")

            # 清空当前页面
            if self.pages_dir.exists():
                for page_file in self.pages_dir.glob("*.md"):
                    page_file.unlink()

            # 恢复备份
            for page_file in backup_dir.glob("*.md"):
                shutil.copy2(page_file, self.pages_dir / page_file.name)

            # 恢复数据库
            db_backup = backup_dir / "gbrain.db"
            if db_backup.exists():
                shutil.copy2(db_backup, self.brain_dir / "gbrain.db")

            return True

        except Exception:
            return False

    def delete_backup(self, backup_name: str) -> bool:
        """删除备份"""
        backup_dir = self.backup_dir / backup_name
        if not backup_dir.exists():
            return False

        try:
            shutil.rmtree(backup_dir)
            return True
        except Exception:
            return False

    # === 迁移工具 ===

    def migrate_from_hermes(self) -> SyncResult:
        """
        从 Hermes 的旧记忆系统迁移

        迁移：
        - MEMORY.md -> originals
        - USER.md -> preferences
        - daily logs -> conversations
        """
        result = SyncResult(status=SyncStatus.SYNCING, message="迁移中...")

        try:
            from core.memory_manager import MemoryManager

            memory = MemoryManager()

            # 迁移 MEMORY.md
            mem_content = memory.get_memory()
            if mem_content:
                page = self.page_manager.create_page(
                    title="Hermes 长期记忆",
                    category=MemoryCategory.ORIGINALS,
                    content=mem_content,
                    source="Hermes Memory Manager",
                    tags=["迁移", "历史"]
                )
                result.pages_added += 1

            # 迁移 USER.md
            user_content = memory.get_user_profile()
            if user_content:
                page = self.page_manager.create_page(
                    title="用户画像",
                    category=MemoryCategory.PREFERENCES,
                    content=user_content,
                    source="Hermes User Profile",
                    tags=["迁移", "用户"]
                )
                result.pages_added += 1

            result.status = SyncStatus.SUCCESS
            result.message = f"迁移完成：新增{result.pages_added}页"

        except Exception as e:
            result.status = SyncStatus.FAILED
            result.message = f"迁移失败：{str(e)}"
            result.errors.append(str(e))

        return result
