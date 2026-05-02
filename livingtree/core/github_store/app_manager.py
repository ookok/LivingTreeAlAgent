"""
应用管理器
管理本地已安装的 GitHub Store 应用
"""

import os
import json
import logging
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import asdict

from .models import InstalledApp, RepoInfo, PlatformType

logger = logging.getLogger(__name__)


class AppManager:
    """
    管理本地安装的 GitHub Store 应用

    功能:
    - 记录已安装应用的信息
    - 检测更新
    - 追踪安装历史
    """

    def __init__(self, data_dir: str = "~/.hermes-desktop/github_store"):
        from pathlib import Path
        self.data_dir = Path(os.path.expanduser(data_dir))
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.apps_file = self.data_dir / "installed_apps.json"
        self.history_file = self.data_dir / "install_history.json"
        self.favorites_file = self.data_dir / "favorites.json"
        self.starred_file = self.data_dir / "starred.json"
        self.recent_file = self.data_dir / "recent.json"

        self._apps: Dict[str, InstalledApp] = {}
        self._favorites: List[str] = []  # [owner/repo, ...]
        self._starred: List[str] = []
        self._recent: List[str] = []

        self._load()

    def _load(self):
        """加载数据"""
        # 加载已安装应用
        if self.apps_file.exists():
            try:
                with open(self.apps_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        v["installed_at"] = datetime.fromisoformat(v["installed_at"])
                        self._apps[k] = InstalledApp(**v)
            except Exception as e:
                logger.warning(f"加载已安装应用失败: {e}")

        # 加载收藏
        if self.favorites_file.exists():
            try:
                with open(self.favorites_file, "r", encoding="utf-8") as f:
                    self._favorites = json.load(f)
            except Exception:
                pass

        # 加载星标
        if self.starred_file.exists():
            try:
                with open(self.starred_file, "r", encoding="utf-8") as f:
                    self._starred = json.load(f)
            except Exception:
                pass

        # 加载最近浏览
        if self.recent_file.exists():
            try:
                with open(self.recent_file, "r", encoding="utf-8") as f:
                    self._recent = json.load(f)
            except Exception:
                pass

    def _save(self):
        """保存数据"""
        # 保存已安装应用
        try:
            data = {k: asdict(v) for k, v in self._apps.items()}
            with open(self.apps_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"保存已安装应用失败: {e}")

        # 保存收藏
        with open(self.favorites_file, "w", encoding="utf-8") as f:
            json.dump(self._favorites, f, ensure_ascii=False, indent=2)

        # 保存星标
        with open(self.starred_file, "w", encoding="utf-8") as f:
            json.dump(self._starred, f, ensure_ascii=False, indent=2)

        # 保存最近浏览
        with open(self.recent_file, "w", encoding="utf-8") as f:
            json.dump(self._recent[:100], f, ensure_ascii=False, indent=2)

    # ── 已安装应用管理 ──────────────────────────────────────────────

    def get_installed_apps(self) -> List[InstalledApp]:
        """获取所有已安装的应用"""
        return list(self._apps.values())

    def get_app(self, full_name: str) -> Optional[InstalledApp]:
        """获取指定应用"""
        return self._apps.get(full_name)

    def is_installed(self, full_name: str) -> bool:
        """检查应用是否已安装"""
        return full_name in self._apps

    def install_app(self, repo: RepoInfo, version: str, install_path: str,
                    asset_name: str, asset_size: int, platform: PlatformType,
                    architecture: Optional[str], download_url: str,
                    notes: str = ""):
        """
        记录应用安装

        Args:
            repo: 仓库信息
            version: 安装的版本
            install_path: 安装路径
            asset_name: 资源文件名
            asset_size: 资源大小
            platform: 平台
            architecture: 架构
            download_url: 下载地址
            notes: 备注
        """
        app = InstalledApp(
            repo_full_name=repo.full_name,
            installed_version=version,
            installed_at=datetime.now(),
            install_path=install_path,
            asset_name=asset_name,
            asset_size=asset_size,
            platform=platform,
            architecture=architecture,
            current_version=version,
            update_available=False,
            download_url=download_url,
            notes=notes,
        )

        self._apps[repo.full_name] = app
        self._save()

        # 记录历史
        self._add_history(repo.full_name, "install", version)

        logger.info(f"记录应用安装: {repo.full_name} v{version}")

    def update_app_version(self, full_name: str, new_version: str,
                           new_install_path: str, download_url: str):
        """更新应用版本"""
        if full_name in self._apps:
            app = self._apps[full_name]
            app.installed_version = new_version
            app.current_version = new_version
            app.update_available = False
            app.install_path = new_install_path
            app.download_url = download_url
            self._save()

            self._add_history(full_name, "update", new_version)
            logger.info(f"更新应用版本: {full_name} -> v{new_version}")

    def uninstall_app(self, full_name: str):
        """卸载应用 (从记录中移除)"""
        if full_name in self._apps:
            version = self._apps[full_name].installed_version
            del self._apps[full_name]
            self._save()

            self._add_history(full_name, "uninstall", version)
            logger.info(f"卸载应用: {full_name}")

    def check_updates(self, updates: Dict[str, str]):
        """
        批量检查更新

        Args:
            updates: {full_name: latest_version, ...}
        """
        for full_name, latest_version in updates.items():
            if full_name in self._apps:
                app = self._apps[full_name]
                if app.installed_version != latest_version:
                    app.current_version = latest_version
                    app.update_available = True

        self._save()

    # ── 收藏管理 ────────────────────────────────────────────────────

    def get_favorites(self) -> List[str]:
        """获取收藏列表"""
        return self._favorites.copy()

    def add_favorite(self, full_name: str):
        """添加收藏"""
        if full_name not in self._favorites:
            self._favorites.append(full_name)
            self._save()
            logger.info(f"添加收藏: {full_name}")

    def remove_favorite(self, full_name: str):
        """移除收藏"""
        if full_name in self._favorites:
            self._favorites.remove(full_name)
            self._save()
            logger.info(f"移除收藏: {full_name}")

    def is_favorite(self, full_name: str) -> bool:
        """是否已收藏"""
        return full_name in self._favorites

    def toggle_favorite(self, full_name: str) -> bool:
        """切换收藏状态"""
        if full_name in self._favorites:
            self._favorites.remove(full_name)
            result = False
        else:
            self._favorites.append(full_name)
            result = True
        self._save()
        return result

    # ── 星标管理 ────────────────────────────────────────────────────

    def get_starred(self) -> List[str]:
        """获取星标列表"""
        return self._starred.copy()

    def add_starred(self, full_name: str):
        """添加星标"""
        if full_name not in self._starred:
            self._starred.append(full_name)
            self._save()

    def remove_starred(self, full_name: str):
        """移除星标"""
        if full_name in self._starred:
            self._starred.remove(full_name)
            self._save()

    def is_starred(self, full_name: str) -> bool:
        """是否已星标"""
        return full_name in self._starred

    # ── 最近浏览 ────────────────────────────────────────────────────

    def get_recent(self, limit: int = 50) -> List[str]:
        """获取最近浏览"""
        return self._recent[:limit]

    def add_recent(self, full_name: str):
        """添加最近浏览"""
        # 移除已存在的
        if full_name in self._recent:
            self._recent.remove(full_name)

        # 添加到最前面
        self._recent.insert(0, full_name)

        # 限制数量
        self._recent = self._recent[:100]
        self._save()

    # ── 安装历史 ────────────────────────────────────────────────────

    def _add_history(self, full_name: str, action: str, version: str):
        """添加历史记录"""
        history_file = self.data_dir / "history" / f"{hashlib.md5(full_name.encode()).hexdigest()[:8]}.json"
        history_file.parent.mkdir(parents=True, exist_ok=True)

        history = []
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                pass

        history.append({
            "action": action,
            "version": version,
            "timestamp": datetime.now().isoformat(),
        })

        # 只保留最近 50 条
        history = history[-50:]

        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def get_history(self, full_name: str) -> List[Dict]:
        """获取安装历史"""
        history_file = self.data_dir / "history" / f"{hashlib.md5(full_name.encode()).hexdigest()[:8]}.json"
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    # ── 统计信息 ────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_size = sum(a.asset_size for a in self._apps.values())

        platform_counts = {}
        for app in self._apps.values():
            p = app.platform.value
            platform_counts[p] = platform_counts.get(p, 0) + 1

        return {
            "total_apps": len(self._apps),
            "total_favorites": len(self._favorites),
            "total_starred": len(self._starred),
            "total_recent": len(self._recent),
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / 1024**3, 2),
            "platform_counts": platform_counts,
            "update_available_count": sum(1 for a in self._apps.values() if a.update_available),
        }
