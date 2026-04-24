"""
智能升级管理系统 - Smart Upgrade Manager

功能：
1. 版本兼容性检测
2. 用户自定义保护
3. 智能升级策略
4. 升级预览与确认
5. 回滚机制
"""

import json
import shutil
import os
import zipfile
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pathlib import Path
import hashlib


class UpgradeStrategy(Enum):
    """升级策略"""
    PRESERVE_ALL = "preserve_all"      # 保留所有用户自定义
    SELECTIVE_MERGE = "selective_merge" # 选择性合并
    FRESH_INSTALL = "fresh_install"     # 全新安装
    AUTO = "auto"                       # 自动选择


class UpgradeStatus(Enum):
    """升级状态"""
    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    PREPARING = "preparing"
    UPGRADING = "upgrading"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ItemType(Enum):
    """项目类型"""
    FORM_TEMPLATE = "form_template"
    USER_SCRIPT = "user_script"
    UI_CONFIG = "ui_config"
    WORKFLOW_DEF = "workflow_def"
    CUSTOM_COMPONENT = "custom_component"
    USER_DATA = "user_data"


@dataclass
class VersionInfo:
    """版本信息"""
    version: str = ""
    release_date: str = ""
    min_compatible_version: str = ""  # 最低兼容版本
    size: int = 0  # bytes
    checksum: str = ""
    download_url: str = ""


@dataclass
class UpgradePackage:
    """升级包信息"""
    id: str = ""
    from_version: str = ""
    to_version: str = ""

    # 内容
    new_features: List[str] = field(default_factory=list)
    bug_fixes: List[str] = field(default_factory=list)
    breaking_changes: List[str] = field(default_factory=list)
    deprecated_items: List[str] = field(default_factory=list)

    # 文件列表
    files_to_add: List[str] = field(default_factory=list)
    files_to_update: List[str] = field(default_factory=list)
    files_to_delete: List[str] = field(default_factory=list)

    # 迁移脚本
    migration_scripts: List[Dict] = field(default_factory=list)

    # 元数据
    size: int = 0
    checksum: str = ""
    published_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UserCustomization:
    """用户自定义项"""
    item_id: str = ""
    item_type: str = ""
    name: str = ""
    path: str = ""
    version: str = ""
    protected: bool = True
    auto_migrate: bool = True
    migration_needed: bool = False
    migration_status: str = "pending"  # pending/success/failed/skipped
    migration_error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UpgradePreview:
    """升级预览"""
    strategy: str = UpgradeStrategy.PRESERVE_ALL.value
    affected_items: Dict[str, List[str]] = field(default_factory=list)

    # 变更统计
    new_files_count: int = 0
    updated_files_count: int = 0
    deleted_files_count: int = 0

    # 用户自定义影响
    preserved_items: List[str] = field(default_factory=list)
    modified_items: List[str] = field(default_factory=list)
    lost_items: List[str] = field(default_factory=list)

    # 风险评估
    risk_level: str = "low"  # low/medium/high/critical
    risk_factors: List[str] = field(default_factory=list)

    # 迁移需求
    migration_steps: List[Dict] = field(default_factory=list)
    estimated_time_seconds: int = 0

    # 兼容性
    compatibility_issues: List[str] = field(default_factory=list)
    rollback_available: bool = True

    # 建议
    recommendation: str = ""
    warnings: List[str] = field(default_factory=list)


@dataclass
class UpgradeState:
    """升级状态"""
    status: str = UpgradeStatus.IDLE.value
    current_version: str = ""
    target_version: str = ""

    # 进度
    progress: float = 0.0  # 0-100
    current_step: str = ""
    steps_completed: int = 0
    steps_total: int = 0

    # 备份
    backup_path: Optional[str] = None
    backup_created_at: Optional[str] = None

    # 日志
    logs: List[Dict] = field(default_factory=list)

    # 错误
    error: Optional[str] = None
    error_details: Optional[Dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


class UserCustomizationProtector:
    """用户自定义内容保护"""

    # 受保护的目录
    PROTECTED_DIRS = {
        "forms": "用户自定义表单",
        "scripts": "用户生成脚本",
        "templates": "UI模板",
        "configs": "个性化配置",
        "workflows": "工作流定义",
        "data": "表单提交数据",
        "custom_components": "自定义组件",
        "themes": "自定义主题",
    }

    def __init__(self, user_data_home: str = None):
        if user_data_home is None:
            user_data_home = Path("~/.hermes/user_data").expanduser()

        self.user_data_home = Path(user_data_home)
        self.protected_marker = ".protected"

    def setup_protected_structure(self):
        """建立受保护的用户数据目录"""
        for folder, desc in self.PROTECTED_DIRS.items():
            folder_path = self.user_data_home / folder
            folder_path.mkdir(parents=True, exist_ok=True)

            # 写入保护标记文件
            marker_file = folder_path / self.protected_marker
            if not marker_file.exists():
                with open(marker_file, "w", encoding="utf-8") as f:
                    f.write(f"# 用户{desc}\n")
                    f.write(f"# 系统更新时会保留此目录及其内容\n")
                    f.write(f"# 创建时间: {datetime.now().isoformat()}\n")

    def scan_customizations(self) -> List[UserCustomization]:
        """扫描用户自定义项"""
        customizations = []

        if not self.user_data_home.exists():
            return customizations

        for folder in self.PROTECTED_DIRS.keys():
            folder_path = self.user_data_home / folder
            if not folder_path.exists():
                continue

            for item_path in folder_path.rglob("*"):
                if item_path.is_file() and not item_path.name.startswith("."):
                    item_type = self._get_item_type(folder, item_path)

                    customizations.append(UserCustomization(
                        item_id=self._compute_item_id(item_path),
                        item_type=item_type,
                        name=item_path.stem,
                        path=str(item_path.relative_to(self.user_data_home)),
                        version="1.0.0",  # 默认版本
                        protected=True
                    ))

        return customizations

    def _get_item_type(self, folder: str, item_path: Path) -> str:
        """获取项目类型"""
        type_mapping = {
            "forms": ItemType.FORM_TEMPLATE.value,
            "scripts": ItemType.USER_SCRIPT.value,
            "templates": ItemType.UI_CONFIG.value,
            "configs": ItemType.UI_CONFIG.value,
            "workflows": ItemType.WORKFLOW_DEF.value,
            "data": ItemType.USER_DATA.value,
            "custom_components": ItemType.CUSTOM_COMPONENT.value,
            "themes": ItemType.UI_CONFIG.value,
        }
        return type_mapping.get(folder, ItemType.USER_DATA.value)

    def _compute_item_id(self, item_path: Path) -> str:
        """计算项目ID"""
        content = str(item_path.relative_to(self.user_data_home))
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def backup_customizations(self, backup_path: Path) -> bool:
        """备份用户自定义"""
        if not self.user_data_home.exists():
            return False

        backup_path.mkdir(parents=True, exist_ok=True)

        try:
            for folder in self.PROTECTED_DIRS.keys():
                src = self.user_data_home / folder
                dst = backup_path / folder

                if src.exists():
                    shutil.copytree(src, dst, dirs_exist_ok=True)

            # 写入备份清单
            manifest = {
                "backup_at": datetime.now().isoformat(),
                "items": [c.to_dict() for c in self.scan_customizations()]
            }
            with open(backup_path / "manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            logger.info(f"Backup error: {e}")
            return False

    def restore_customizations(self, backup_path: Path) -> bool:
        """恢复用户自定义"""
        if not backup_path.exists():
            return False

        try:
            manifest_path = backup_path / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

            for folder in self.PROTECTED_DIRS.keys():
                src = backup_path / folder
                dst = self.user_data_home / folder

                if src.exists():
                    # 合并恢复（保留新版文件）
                    self._merge_restore(src, dst)

            return True

        except Exception as e:
            logger.info(f"Restore error: {e}")
            return False

    def _merge_restore(self, src: Path, dst: Path):
        """合并恢复"""
        dst.mkdir(parents=True, exist_ok=True)

        for item in src.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(src)
                dst_file = dst / rel_path

                # 如果目标不存在或源更新，则复制
                if not dst_file.exists() or os.path.getmtime(item) > os.path.getmtime(dst_file):
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dst_file)


class VersionCompatibilityAdapter:
    """版本兼容性适配器"""

    def __init__(self):
        # 兼容性规则
        self.compatibility_rules: Dict[str, Dict] = {}
        self._load_builtin_rules()

    def _load_builtin_rules(self):
        """加载内置规则"""
        # v1.0.0 -> v2.0.0 规则
        self.compatibility_rules["1.0.0->2.0.0"] = {
            "breaking_changes": [
                {"field": "config.api_endpoint", "action": "rename", "new_field": "config.api.url"}
            ],
            "migrations": [
                {"type": "field_rename", "from": "config.api_endpoint", "to": "config.api.url"}
            ]
        }

    def adapt_form_for_version(
        self,
        form_config: dict,
        target_version: str
    ) -> dict:
        """适配表单到特定版本"""
        current_version = form_config.get("version", "1.0.0")

        if current_version == target_version:
            return form_config

        # 查找迁移路径
        migration_path = self._find_migration_path(current_version, target_version)

        adapted = form_config.copy()
        for from_ver, to_ver in migration_path:
            adapter = self._get_version_adapter(from_ver, to_ver)
            adapted = adapter.adapt(adapted)

        return adapted

    def _find_migration_path(
        self,
        from_version: str,
        to_version: str
    ) -> List[tuple]:
        """查找迁移路径"""
        # 简化的线性迁移
        if from_version == "1.0.0" and to_version == "2.0.0":
            return [("1.0.0", "2.0.0")]

        return [(from_version, to_version)]

    def _get_version_adapter(self, from_ver: str, to_ver: str):
        """获取版本适配器"""
        key = f"{from_ver}->{to_ver}"

        if key in self.compatibility_rules:
            rules = self.compatibility_rules[key]
            return VersionAdapter(rules)

        return DefaultVersionAdapter()


class VersionAdapter:
    """版本适配器"""

    def __init__(self, rules: dict):
        self.rules = rules

    def adapt(self, config: dict) -> dict:
        """适配配置"""
        adapted = config.copy()

        # 应用字段重命名
        for migration in self.rules.get("migrations", []):
            if migration["type"] == "field_rename":
                from_field = migration["from"]
                to_field = migration["to"]

                # 递归重命名字段
                adapted = self._rename_field(adapted, from_field, to_field)

        # 更新版本
        adapted["version"] = self.rules.get("to_version", "unknown")

        return adapted

    def _rename_field(self, obj: Any, from_path: str, to_path: str) -> Any:
        """重命名字段"""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key == from_path:
                    result[to_path] = self._rename_field(value, from_path, to_path)
                else:
                    result[key] = self._rename_field(value, from_path, to_path)
            return result
        elif isinstance(obj, list):
            return [self._rename_field(item, from_path, to_path) for item in obj]
        else:
            return obj


class DefaultVersionAdapter:
    """默认版本适配器"""

    def adapt(self, config: dict) -> dict:
        """默认适配（仅更新版本）"""
        config["version"] = "adapted"
        return config


class SmartUpgradeManager:
    """智能升级管理器"""

    def __init__(self, app_home: str = None, user_data_home: str = None):
        if app_home is None:
            app_home = Path("~/.hermes").expanduser()

        self.app_home = Path(app_home)
        self.app_home.mkdir(parents=True, exist_ok=True)

        # 组件
        self.customization_protector = UserCustomizationProtector(user_data_home)
        self.compatibility_adapter = VersionCompatibilityAdapter()

        # 状态
        self.state = UpgradeState()
        self.state.current_version = self._get_current_version()

        # 回调
        self._callbacks: Dict[str, List[Callable]] = {}

    def _get_current_version(self) -> str:
        """获取当前版本"""
        version_file = self.app_home / "version.txt"
        if version_file.exists():
            return version_file.read_text().strip()
        return "1.0.0"

    def on(self, event: str, callback: Callable):
        """注册回调"""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def _emit(self, event: str, data: dict = None):
        """触发事件"""
        callbacks = self._callbacks.get(event, [])
        for cb in callbacks:
            try:
                cb(data or {})
            except Exception as e:
                logger.info(f"Upgrade callback error: {e}")

    async def check_for_updates(self) -> Optional[UpgradePackage]:
        """检查更新"""
        self.state.status = UpgradeStatus.CHECKING.value
        self._emit("checking")

        # 模拟检查更新
        # 实际应该从服务器获取
        await self._simulate_delay(0.5)

        # 模拟返回更新包
        if self.state.current_version == "1.0.0":
            return UpgradePackage(
                id="pkg_001",
                from_version="1.0.0",
                to_version="2.0.0",
                new_features=[
                    "全新的智能表单系统",
                    "工作流引擎升级",
                    "UI模板市场",
                    "自然语言数据查询"
                ],
                bug_fixes=[
                    "修复了若干已知问题"
                ],
                breaking_changes=[
                    "配置文件格式有变化，请备份后升级"
                ],
                published_at=datetime.now().isoformat()
            )

        return None

    async def generate_preview(
        self,
        package: UpgradePackage,
        strategy: str = UpgradeStrategy.PRESERVE_ALL.value
    ) -> UpgradePreview:
        """生成升级预览"""
        preview = UpgradePreview(strategy=strategy)

        # 分析影响
        preview.new_files_count = len(package.files_to_add)
        preview.updated_files_count = len(package.files_to_update)
        preview.deleted_files_count = len(package.files_to_delete)

        # 扫描用户自定义
        customizations = self.customization_protector.scan_customizations()
        preview.preserved_items = [c.name for c in customizations]

        # 检查兼容性
        if package.breaking_changes:
            preview.risk_level = "medium"
            preview.risk_factors.append("存在破坏性变更")
            preview.warnings.append("建议在升级前备份重要数据")

        # 生成迁移步骤
        preview.migration_steps = self._generate_migration_steps(package)

        # 估计时间
        preview.estimated_time_seconds = (
            preview.new_files_count * 0.1 +
            preview.updated_files_count * 0.2 +
            len(preview.migration_steps) * 2
        )

        # 建议
        preview.recommendation = "推荐使用「保留所有用户自定义」策略"

        self._emit("preview_generated", {"preview": preview})
        return preview

    def _generate_migration_steps(self, package: UpgradePackage) -> List[Dict]:
        """生成迁移步骤"""
        steps = []

        if package.migration_scripts:
            for script in package.migration_scripts:
                steps.append({
                    "id": script.get("id", ""),
                    "description": script.get("description", ""),
                    "type": "script",
                    "estimated_time": 2
                })

        if package.breaking_changes:
            steps.append({
                "id": "backup_config",
                "description": "备份配置文件",
                "type": "backup",
                "estimated_time": 1
            })

        return steps

    async def perform_upgrade(
        self,
        package: UpgradePackage,
        strategy: str = UpgradeStrategy.PRESERVE_ALL.value,
        preview: UpgradePreview = None
    ) -> bool:
        """执行升级"""
        self.state.status = UpgradeStatus.PREPARING.value
        self.state.target_version = package.to_version
        self._emit("preparing")

        try:
            # 1. 备份
            self._update_progress(5, "正在创建备份...")
            backup_path = self.app_home / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path.mkdir(parents=True, exist_ok=True)

            if strategy == UpgradeStrategy.PRESERVE_ALL.value:
                self.customization_protector.backup_customizations(backup_path)

            self.state.backup_path = str(backup_path)
            self.state.backup_created_at = datetime.now().isoformat()

            # 2. 准备升级
            self._update_progress(20, "正在准备升级文件...")
            await self._simulate_delay(0.5)

            # 3. 执行迁移
            self._update_progress(40, "正在执行数据迁移...")
            if preview and preview.migration_steps:
                for i, step in enumerate(preview.migration_steps):
                    self._update_progress(
                        40 + int(30 * (i + 1) / len(preview.migration_steps)),
                        f"正在执行: {step['description']}"
                    )
                    await self._simulate_delay(0.3)

            # 4. 更新文件
            self._update_progress(70, "正在更新系统文件...")
            await self._simulate_delay(0.5)

            # 5. 清理
            self._update_progress(90, "正在清理...")
            await self._simulate_delay(0.3)

            # 6. 完成
            self._update_progress(100, "升级完成！")
            self.state.status = UpgradeStatus.COMPLETED.value

            # 更新版本
            version_file = self.app_home / "version.txt"
            version_file.write_text(package.to_version)
            self.state.current_version = package.to_version

            self._emit("completed", {
                "from_version": package.from_version,
                "to_version": package.to_version
            })

            return True

        except Exception as e:
            self.state.status = UpgradeStatus.FAILED.value
            self.state.error = str(e)
            self._emit("failed", {"error": str(e)})
            return False

    async def rollback(self) -> bool:
        """回滚升级"""
        if not self.state.backup_path:
            return False

        self.state.status = UpgradeStatus.UPGRADING.value
        self._emit("rolling_back")

        try:
            # 恢复用户自定义
            self.customization_protector.restore_customizations(Path(self.state.backup_path))

            # 恢复版本
            version_file = self.app_home / "version.txt"
            version_file.write_text(self.state.current_version)

            self.state.status = UpgradeStatus.ROLLED_BACK.value
            self._emit("rolled_back")

            return True

        except Exception as e:
            self.state.error = f"回滚失败: {str(e)}"
            self._emit("rollback_failed", {"error": str(e)})
            return False

    def _update_progress(self, progress: float, step: str):
        """更新进度"""
        self.state.progress = progress
        self.state.current_step = step
        self._emit("progress", {
            "progress": progress,
            "step": step
        })

    async def _simulate_delay(self, seconds: float):
        """模拟延迟"""
        import asyncio
from core.logger import get_logger
logger = get_logger('upgrade_manager.__init__')

        await asyncio.sleep(seconds)

    def get_upgrade_state(self) -> UpgradeState:
        """获取升级状态"""
        return self.state


class UpgradeNotificationManager:
    """升级通知管理器"""

    def __init__(self, store_path: str = None):
        if store_path is None:
            store_path = Path("~/.hermes/upgrade_notifications").expanduser()

        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

        self._notifications_file = self.store_path / "notifications.json"
        self._notifications: List[Dict] = []
        self._load_notifications()

    def _load_notifications(self):
        """加载通知"""
        if self._notifications_file.exists():
            with open(self._notifications_file, "r", encoding="utf-8") as f:
                self._notifications = json.load(f)

    def _save_notifications(self):
        """保存通知"""
        with open(self._notifications_file, "w", encoding="utf-8") as f:
            json.dump(self._notifications, f, ensure_ascii=False, indent=2)

    def add_notification(self, update_info: dict):
        """添加通知"""
        notification = {
            "id": update_info.get("id", ""),
            "version": update_info.get("version", ""),
            "title": update_info.get("title", ""),
            "description": update_info.get("description", ""),
            "new_features": update_info.get("new_features", []),
            "bug_fixes": update_info.get("bug_fixes", []),
            "breaking_changes": update_info.get("breaking_changes", []),
            "created_at": datetime.now().isoformat(),
            "acknowledged": False,
            "acknowledged_at": None,
            "withdraw_votes": [],  # 投票撤回的用户ID列表
            "status": "available"
        }

        self._notifications.append(notification)
        self._save_notifications()

    def acknowledge(self, notification_id: str, user_id: str) -> bool:
        """确认通知"""
        for n in self._notifications:
            if n["id"] == notification_id:
                n["acknowledged"] = True
                n["acknowledged_at"] = datetime.now().isoformat()
                self._save_notifications()
                return True
        return False

    def vote_withdraw(self, notification_id: str, user_id: str) -> bool:
        """投票撤回"""
        for n in self._notifications:
            if n["id"] == notification_id:
                if user_id not in n["withdraw_votes"]:
                    n["withdraw_votes"].append(user_id)

                    # 检查是否达到阈值
                    if len(n["withdraw_votes"]) >= 10:
                        n["status"] = "withdrawn"

                    self._save_notifications()
                    return True
        return False

    def get_pending_notifications(self, user_id: str = None) -> List[Dict]:
        """获取待处理通知"""
        pending = []

        for n in self._notifications:
            if n["status"] == "withdrawn":
                continue

            # 检查用户是否已确认
            if user_id and n.get("acknowledged_by") and user_id in n["acknowledged_by"]:
                continue

            pending.append(n)

        return pending

    def has_new_version_banner(self, user_id: str = None) -> bool:
        """是否有新版本标题栏提示"""
        pending = self.get_pending_notifications(user_id)
        return len(pending) > 0


# 全局实例
_upgrade_manager: Optional[SmartUpgradeManager] = None
_notification_manager: Optional[UpgradeNotificationManager] = None


def get_upgrade_manager() -> SmartUpgradeManager:
    """获取升级管理器"""
    global _upgrade_manager
    if _upgrade_manager is None:
        _upgrade_manager = SmartUpgradeManager()
    return _upgrade_manager


def get_notification_manager() -> UpgradeNotificationManager:
    """获取通知管理器"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = UpgradeNotificationManager()
    return _notification_manager