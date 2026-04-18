"""
Profile 多实例管理
参考 hermes-agent 的 profiles.py 设计

每个 Profile 是独立的 Hermes 实例，有自己的：
- config.yaml
- .env (API Keys)
- memories/
- sessions/
- skills/
- logs/
"""

import json
import os
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any


# ── Constants ────────────────────────────────────────────────────────────────

_PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

_PROFILE_DIRS = [
    "memories",
    "sessions",
    "skills",
    "skins",
    "logs",
    "plans",
    "workspace",
    "cron",
]

_CLONE_CONFIG_FILES = [
    "config.yaml",
    ".env",
    "SOUL.md",
]

_RESERVED_NAMES = frozenset({
    "hermes", "default", "test", "tmp", "root", "sudo",
})

_HERMES_SUBCOMMANDS = frozenset({
    "chat", "model", "gateway", "setup", "status", "config",
    "profile", "plugins", "skills", "tools", "mcp", "sessions",
})


# ── Profile Info ─────────────────────────────────────────────────────────────

@dataclass
class ProfileInfo:
    """Profile 信息"""
    name: str
    path: Path
    is_default: bool
    gateway_running: bool
    model: Optional[str] = None
    provider: Optional[str] = None
    has_env: bool = False
    skill_count: int = 0
    alias_path: Optional[Path] = None


# ── Path Helpers ─────────────────────────────────────────────────────────────

def _get_profiles_root() -> Path:
    """Profile 根目录"""
    return Path.home() / ".hermes-desktop" / "profiles"


def _get_default_hermes_home() -> Path:
    """默认 HERMES_HOME 目录"""
    return Path.home() / ".hermes-desktop"


def _get_active_profile_file() -> Path:
    """活跃 Profile 文件"""
    return _get_default_hermes_home() / "active_profile"


def _get_wrapper_dir() -> Path:
    """Wrapper 脚本目录"""
    return Path.home() / ".local" / "bin"


# ── Validation ─────────────────────────────────────────────────────────────

def validate_profile_name(name: str) -> bool:
    """验证 Profile 名称是否合法"""
    if name == "default":
        return True
    return bool(_PROFILE_ID_RE.match(name))


def get_profile_dir(name: str) -> Path:
    """获取 Profile 目录"""
    if name == "default":
        return _get_default_hermes_home()
    return _get_profiles_root() / name


def profile_exists(name: str) -> bool:
    """检查 Profile 是否存在"""
    if name == "default":
        return True
    return get_profile_dir(name).is_dir()


# ── CRUD Operations ────────────────────────────────────────────────────────

def list_profiles() -> List[ProfileInfo]:
    """列出所有 Profile"""
    profiles = []
    
    # 默认 Profile
    default_home = _get_default_hermes_home()
    if default_home.is_dir():
        model, provider = _read_config_model(default_home)
        profiles.append(ProfileInfo(
            name="default",
            path=default_home,
            is_default=True,
            gateway_running=_check_gateway_running(default_home),
            model=model,
            provider=provider,
            has_env=(default_home / ".env").exists(),
            skill_count=_count_skills(default_home),
        ))
    
    # 命名 Profiles
    profiles_root = _get_profiles_root()
    if profiles_root.is_dir():
        for entry in sorted(profiles_root.iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name
            if not _PROFILE_ID_RE.match(name):
                continue
            model, provider = _read_config_model(entry)
            alias_path = _get_wrapper_dir() / name
            profiles.append(ProfileInfo(
                name=name,
                path=entry,
                is_default=False,
                gateway_running=_check_gateway_running(entry),
                model=model,
                provider=provider,
                has_env=(entry / ".env").exists(),
                skill_count=_count_skills(entry),
                alias_path=alias_path if alias_path.exists() else None,
            ))
    
    return profiles


def create_profile(
    name: str,
    clone_from: Optional[str] = None,
) -> Path:
    """创建新 Profile"""
    if not validate_profile_name(name):
        raise ValueError(f"Invalid profile name: {name}")
    
    if name == "default":
        raise ValueError("Cannot create 'default' profile")
    
    if profile_exists(name):
        raise FileExistsError(f"Profile '{name}' already exists")
    
    profile_dir = get_profile_dir(name)
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建子目录
    for subdir in _PROFILE_DIRS:
        (profile_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    # 克隆配置
    if clone_from:
        source_dir = get_profile_dir(clone_from)
        if source_dir.is_dir():
            for filename in _CLONE_CONFIG_FILES:
                src = source_dir / filename
                if src.exists():
                    shutil.copy2(src, profile_dir / filename)
    
    return profile_dir


def delete_profile(name: str) -> bool:
    """删除 Profile"""
    if not validate_profile_name(name):
        raise ValueError(f"Invalid profile name: {name}")
    
    if name == "default":
        raise ValueError("Cannot delete 'default' profile")
    
    profile_dir = get_profile_dir(name)
    if not profile_dir.is_dir():
        raise FileNotFoundError(f"Profile '{name}' does not exist")
    
    # 停止 Gateway
    if _check_gateway_running(profile_dir):
        _stop_gateway_process(profile_dir)
    
    # 删除目录
    shutil.rmtree(profile_dir)
    
    # 清除活跃 Profile
    if get_active_profile() == name:
        set_active_profile("default")
    
    return True


def rename_profile(old_name: str, new_name: str) -> Path:
    """重命名 Profile"""
    if old_name == "default" or new_name == "default":
        raise ValueError("Cannot rename 'default' profile")
    
    if not validate_profile_name(old_name) or not validate_profile_name(new_name):
        raise ValueError("Invalid profile name")
    
    old_dir = get_profile_dir(old_name)
    new_dir = get_profile_dir(new_name)
    
    if not old_dir.is_dir():
        raise FileNotFoundError(f"Profile '{old_name}' does not exist")
    
    if new_dir.exists():
        raise FileExistsError(f"Profile '{new_name}' already exists")
    
    # 停止 Gateway
    if _check_gateway_running(old_dir):
        _stop_gateway_process(old_dir)
    
    # 重命名
    old_dir.rename(new_dir)
    
    # 更新活跃 Profile
    if get_active_profile() == old_name:
        set_active_profile(new_name)
    
    return new_dir


# ── Active Profile ──────────────────────────────────────────────────────────

def get_active_profile() -> str:
    """获取当前活跃 Profile"""
    path = _get_active_profile_file()
    try:
        name = path.read_text().strip()
        return name if name else "default"
    except (FileNotFoundError, UnicodeDecodeError, OSError):
        return "default"


def set_active_profile(name: str) -> None:
    """设置活跃 Profile"""
    if not validate_profile_name(name):
        raise ValueError(f"Invalid profile name: {name}")
    
    if name != "default" and not profile_exists(name):
        raise FileNotFoundError(f"Profile '{name}' does not exist")
    
    path = _get_active_profile_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if name == "default":
        path.unlink(missing_ok=True)
    else:
        path.write_text(name + "\n")


# ── Import / Export ────────────────────────────────────────────────────────

def export_profile(name: str, output_path: str) -> Path:
    """导出 Profile 到压缩包"""
    import tempfile
    
    if not validate_profile_name(name):
        raise ValueError(f"Invalid profile name: {name}")
    
    profile_dir = get_profile_dir(name)
    if not profile_dir.is_dir():
        raise FileNotFoundError(f"Profile '{name}' does not exist")
    
    output = Path(output_path)
    base = str(output).removesuffix(".zip").removesuffix(".tar.gz")
    
    # 排除敏感文件
    cred_files = {"auth.json", ".env"}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        staged = Path(tmpdir) / name
        shutil.copytree(
            profile_dir,
            staged,
            ignore=lambda d, contents: cred_files & set(contents),
        )
        
        result = shutil.make_archive(base, "gztar", tmpdir, name)
        return Path(result)


def import_profile(archive_path: str, name: Optional[str] = None) -> Path:
    """从压缩包导入 Profile"""
    import tarfile
    
    archive = Path(archive_path)
    if not archive.exists():
        raise FileNotFoundError(f"Archive not found: {archive}")
    
    # 读取顶层目录
    with tarfile.open(archive, "r:gz") as tf:
        members = tf.getmembers()
        if not members:
            raise ValueError("Empty archive")
        
        top_name = members[0].name.split("/")[0]
    
    inferred_name = name or top_name
    
    if inferred_name == "default":
        raise ValueError("Cannot import as 'default'")
    
    if not validate_profile_name(inferred_name):
        raise ValueError(f"Invalid profile name: {inferred_name}")
    
    profile_dir = get_profile_dir(inferred_name)
    if profile_dir.exists():
        raise FileExistsError(f"Profile '{inferred_name}' already exists")
    
    # 解压
    profiles_root = _get_profiles_root()
    profiles_root.mkdir(parents=True, exist_ok=True)
    
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(profiles_root)
    
    # 重命名
    extracted = profiles_root / top_name
    if extracted != profile_dir and extracted.exists():
        extracted.rename(profile_dir)
    
    return profile_dir


# ── Private Helpers ────────────────────────────────────────────────────────

def _read_config_model(profile_dir: Path) -> tuple:
    """读取 Profile 的模型配置"""
    config_path = profile_dir / "config.yaml"
    if not config_path.exists():
        return None, None
    
    try:
        import yaml
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}
        model_cfg = cfg.get("model", {})
        if isinstance(model_cfg, str):
            return model_cfg, None
        if isinstance(model_cfg, dict):
            return model_cfg.get("default") or model_cfg.get("model"), model_cfg.get("provider")
        return None, None
    except Exception:
        return None, None


def _check_gateway_running(profile_dir: Path) -> bool:
    """检查 Gateway 是否运行"""
    pid_file = profile_dir / "gateway.pid"
    if not pid_file.exists():
        return False
    
    try:
        raw = pid_file.read_text().strip()
        if not raw:
            return False
        data = json.loads(raw) if raw.startswith("{") else {"pid": int(raw)}
        pid = int(data["pid"])
        os.kill(pid, 0)  # existence check
        return True
    except (json.JSONDecodeError, KeyError, ValueError, TypeError,
            ProcessLookupError, PermissionError, OSError):
        return False


def _count_skills(profile_dir: Path) -> int:
    """统计已安装的 Skills"""
    skills_dir = profile_dir / "skills"
    if not skills_dir.is_dir():
        return 0
    
    count = 0
    for md in skills_dir.rglob("SKILL.md"):
        if "/.hub/" not in str(md) and "/.git/" not in str(md):
            count += 1
    return count


def _stop_gateway_process(profile_dir: Path) -> None:
    """停止 Gateway 进程"""
    import signal
    
    pid_file = profile_dir / "gateway.pid"
    if not pid_file.exists():
        return
    
    try:
        raw = pid_file.read_text().strip()
        data = json.loads(raw) if raw.startswith("{") else {"pid": int(raw)}
        pid = int(data["pid"])
        os.kill(pid, signal.SIGTERM)
        
        # 等待最多 10 秒
        import time
        for _ in range(20):
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
        
        # 强制终止
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    except Exception:
        pass


# ── Profile Manager Class ──────────────────────────────────────────────────

class ProfileManager:
    """Profile 管理器"""
    
    def __init__(self):
        self.profiles_root = _get_profiles_root()
        self.default_home = _get_default_hermes_home()
        self.active_file = _get_active_profile_file()
    
    def get_current_profile(self) -> str:
        """获取当前 Profile"""
        return get_active_profile()
    
    def get_current_home(self) -> Path:
        """获取当前 HERMES_HOME"""
        name = get_active_profile()
        return get_profile_dir(name)
    
    def switch_profile(self, name: str) -> bool:
        """切换 Profile"""
        try:
            set_active_profile(name)
            return True
        except Exception:
            return False
    
    def get_all_profiles(self) -> List[ProfileInfo]:
        """获取所有 Profile"""
        return list_profiles()
    
    def create_profile(self, name: str, clone_from: Optional[str] = None) -> Path:
        """创建 Profile"""
        return create_profile(name, clone_from)
    
    def delete_profile(self, name: str) -> bool:
        """删除 Profile"""
        return delete_profile(name)
    
    def export_profile(self, name: str, output_path: str) -> Path:
        """导出 Profile"""
        return export_profile(name, output_path)
    
    def import_profile(self, archive_path: str, name: Optional[str] = None) -> Path:
        """导入 Profile"""
        return import_profile(archive_path, name)


# Singleton instance
_profile_manager: Optional[ProfileManager] = None


def get_profile_manager() -> ProfileManager:
    """获取 Profile 管理器单例"""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager
