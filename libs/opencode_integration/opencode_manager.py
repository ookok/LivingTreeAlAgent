"""
OpenCode 集成管理器
===================

集成 OpenCode CLI 和 oh-my-opencode 插件到 LivingTree AI Agent

功能:
1. OpenCode CLI 生命周期管理 (启动/停止/状态)
2. oh-my-opencode 插件自动安装和配置
3. 嵌入式仓库同步 (git pull upstream)
4. 代理进程管理
"""

import os
import json
import subprocess
import threading
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import shutil
import hashlib

# ============================================================================
# 路径配置
# ============================================================================

LIBS_DIR = Path(__file__).parent.parent
OPENCODE_CORE_DIR = LIBS_DIR / "opencode-core"
OHMYOPENCODE_DIR = LIBS_DIR / "oh-my-opencode-plugin"
INTEGRATION_DIR = Path(__file__).parent

# 配置文件路径
OPENCODE_CONFIG_DIR = Path.home() / ".config" / "opencode"
OPENCODE_CONFIG_FILE = OPENCODE_CONFIG_DIR / "opencode.json"


# ============================================================================
# 数据结构
# ============================================================================

class OpenCodeStatus(Enum):
    """OpenCode 运行状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    INSTALLING = "installing"


@dataclass
class OpenCodeConfig:
    """OpenCode 配置"""
    # 模型配置
    default_model: str = "claude-sonnet-4-20250514"
    fallback_model: str = "gpt-4o"
    
    # 代理配置
    enable_agent: bool = True
    agent_timeout: int = 300
    
    # 插件配置
    plugin_dirs: List[str] = field(default_factory=list)
    enable_oh_my_opencode: bool = True
    
    # 工作目录
    work_dir: Optional[str] = None
    
    # 环境变量
    env_vars: Dict[str, str] = field(default_factory=dict)
    
    # oh-my-opencode 配置
    oh_my_opencode_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginInfo:
    """插件信息"""
    name: str
    path: str
    version: Optional[str] = None
    enabled: bool = True
    description: Optional[str] = None


@dataclass
class OpenCodeStatusInfo:
    """状态信息"""
    status: OpenCodeStatus
    pid: Optional[int] = None
    port: Optional[int] = None
    version: Optional[str] = None
    plugins: List[PluginInfo] = field(default_factory=list)
    uptime: float = 0
    error: Optional[str] = None


# ============================================================================
# 异常定义
# ============================================================================

class OpenCodeError(Exception):
    """基础异常"""
    pass


class OpenCodeNotFoundError(OpenCodeError):
    """OpenCode 未安装"""
    pass


class OpenCodeInstallError(OpenCodeError):
    """安装失败"""
    pass


class OpenCodeStartError(OpenCodeError):
    """启动失败"""
    pass


# ============================================================================
# OpenCode CLI 管理器
# ============================================================================

class OpenCodeCLI:
    """OpenCode CLI 生命周期管理"""
    
    def __init__(self, core_dir: Path = OPENCODE_CORE_DIR):
        self.core_dir = core_dir
        self.cli_path = self._find_cli()
        self._process: Optional[subprocess.Popen] = None
        self._start_time: Optional[float] = None
    
    def _find_cli(self) -> Path:
        """查找 OpenCode CLI"""
        # 优先使用本地编译的
        local_cli = self.core_dir / "bin" / "opencode"
        if local_cli.exists():
            return local_cli
        
        # 尝试 PATH 中的 opencode
        try:
            result = subprocess.run(
                ["opencode", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return Path(shutil.which("opencode"))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 尝试安装脚本
        install_script = self.core_dir / "install"
        if install_script.exists():
            return install_script
        
        raise OpenCodeNotFoundError(
            f"OpenCode CLI not found. Core dir: {self.core_dir}"
        )
    
    def install(self, target_dir: Optional[Path] = None) -> bool:
        """安装 OpenCode"""
        if target_dir is None:
            target_dir = Path.home() / ".local" / "bin"
        
        target_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 使用安装脚本
            result = subprocess.run(
                [str(self.cli_path), "-y", str(target_dir)],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(self.core_dir)
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            raise OpenCodeInstallError("Installation timeout")
        except Exception as e:
            raise OpenCodeInstallError(f"Installation failed: {e}")
    
    def version(self) -> Optional[str]:
        """获取版本"""
        try:
            result = subprocess.run(
                ["opencode", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
    
    def start(
        self,
        config: OpenCodeConfig,
        on_output: Optional[Callable[[str], None]] = None
    ) -> bool:
        """启动 OpenCode 交互式会话"""
        if self._process is not None:
            return True
        
        env = os.environ.copy()
        env.update(config.env_vars)
        
        # 设置插件路径
        plugin_paths = [str(OHMYOPENCODE_DIR / "dist" / "index.js")]
        for p in config.plugin_dirs:
            plugin_paths.append(p)
        
        env["OPENCODE_PLUGIN_PATHS"] = ":".join(filter(None, plugin_paths))
        
        try:
            self._process = subprocess.Popen(
                ["opencode"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                cwd=config.work_dir or str(Path.cwd())
            )
            self._start_time = time.time()
            
            # 后台读取输出
            if on_output:
                def reader():
                    while self._process and self._process.poll() is None:
                        line = self._process.stdout.readline()
                        if line:
                            on_output(line)
                
                threading.Thread(target=reader, daemon=True).start()
            
            return True
            
        except Exception as e:
            self._process = None
            raise OpenCodeStartError(f"Failed to start: {e}")
    
    def send(self, command: str) -> bool:
        """发送命令到 OpenCode"""
        if self._process is None or self._process.poll() is not None:
            return False
        
        try:
            self._process.stdin.write(command + "\n")
            self._process.stdin.flush()
            return True
        except Exception:
            return False
    
    def stop(self) -> bool:
        """停止 OpenCode"""
        if self._process is None:
            return True
        
        try:
            self._process.terminate()
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
        finally:
            self._process = None
            self._start_time = None
        
        return True
    
    @property
    def is_running(self) -> bool:
        """检查是否运行中"""
        return self._process is not None and self._process.poll() is None
    
    def status(self) -> OpenCodeStatusInfo:
        """获取状态"""
        status = OpenCodeStatus.RUNNING if self.is_running else OpenCodeStatus.STOPPED
        uptime = time.time() - self._start_time if self._start_time else 0
        
        return OpenCodeStatusInfo(
            status=status,
            pid=self._process.pid if self._process else None,
            version=self.version(),
            uptime=uptime
        )


# ============================================================================
# oh-my-opencode 插件管理器
# ============================================================================

class OhMyOpenCodeManager:
    """oh-my-opencode 插件管理"""
    
    def __init__(self, plugin_dir: Path = OHMYOPENCODE_DIR):
        self.plugin_dir = plugin_dir
        self.dist_dir = plugin_dir / "dist"
        self.config_file = OPENCODE_CONFIG_DIR / "opencode.json"
    
    def is_installed(self) -> bool:
        """检查是否已安装"""
        return self.dist_dir.exists() and (self.dist_dir / "index.js").exists()
    
    def build(self) -> bool:
        """构建插件 (需要 Bun)"""
        if not self.plugin_dir.exists():
            raise OpenCodeError(f"Plugin directory not found: {self.plugin_dir}")
        
        try:
            # 检查 Bun
            subprocess.run(["bun", "--version"], capture_output=True, timeout=10)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # 尝试 npm 作为 fallback
            return self._build_with_npm()
        
        try:
            result = subprocess.run(
                ["bun", "install"],
                cwd=str(self.plugin_dir),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                result = subprocess.run(
                    ["bun", "run", "build"],
                    cwd=str(self.plugin_dir),
                    capture_output=True,
                    text=True,
                    timeout=120
                )
            
            return result.returncode == 0 and self.is_installed()
            
        except subprocess.TimeoutExpired:
            raise OpenCodeError("Build timeout")
        except Exception as e:
            raise OpenCodeError(f"Build failed: {e}")
    
    def _build_with_npm(self) -> bool:
        """使用 npm 构建"""
        try:
            subprocess.run(["npm", "install"], cwd=str(self.plugin_dir), timeout=120)
            subprocess.run(["npm", "run", "build"], cwd=str(self.plugin_dir), timeout=120)
            return self.is_installed()
        except Exception:
            return False
    
    def configure(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """配置 OpenCode 使用本插件"""
        OPENCODE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # 读取现有配置
        existing_config = {}
        if self.config_file.exists():
            try:
                existing_config = json.loads(self.config_file.read_text())
            except Exception:
                pass
        
        # 添加插件路径
        plugin_path = f"file://{self.dist_dir / 'index.js'}"
        if "plugin" not in existing_config:
            existing_config["plugin"] = []
        
        if isinstance(existing_config["plugin"], list):
            if plugin_path not in existing_config["plugin"]:
                existing_config["plugin"].append(plugin_path)
        else:
            existing_config["plugin"] = [plugin_path]
        
        # 合并其他配置
        if config:
            existing_config.update(config)
        
        # 写入配置
        self.config_file.write_text(json.dumps(existing_config, indent=2))
        return True
    
    def sync(self) -> bool:
        """同步上游更新"""
        if not self.plugin_dir.exists():
            return False
        
        try:
            result = subprocess.run(
                ["git", "pull", "origin", "master"],
                cwd=str(self.plugin_dir),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and self.is_installed():
                return self.build()
            
            return False
        except Exception:
            return False


# ============================================================================
# 嵌入式仓库同步管理器
# ============================================================================

class EmbeddedRepoSync:
    """嵌入式仓库同步管理"""
    
    def __init__(self, libs_dir: Path = LIBS_DIR):
        self.libs_dir = libs_dir
        self.remotes = {
            "opencode-core": {
                "dir": self.libs_dir / "opencode-core",
                "url": "https://github.com/opencode-ai/opencode.git",
                "branch": "main"
            },
            "oh-my-opencode": {
                "dir": self.libs_dir / "oh-my-opencode-plugin",
                "url": "https://github.com/code-yeongyu/oh-my-opencode.git",
                "branch": "master"
            },
            "serena-core": {
                "dir": self.libs_dir / "serena-core",
                "url": None,  # 可能已经是 submodule
                "branch": "main"
            }
        }
    
    def sync_all(self, force: bool = False) -> Dict[str, bool]:
        """同步所有嵌入式仓库"""
        results = {}
        
        for name, info in self.remotes.items():
            results[name] = self.sync_repo(name, force=force)
        
        return results
    
    def sync_repo(self, name: str, force: bool = False) -> bool:
        """同步指定仓库"""
        if name not in self.remotes:
            return False
        
        info = self.remotes[name]
        repo_dir = info["dir"]
        
        if not repo_dir.exists():
            return self.clone_repo(name)
        
        try:
            # 获取远程更新
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=str(repo_dir),
                capture_output=True,
                timeout=60
            )
            
            # 拉取更新
            if force:
                subprocess.run(
                    ["git", "reset", "--hard", f"origin/{info['branch']}"],
                    cwd=str(repo_dir),
                    capture_output=True,
                    timeout=60
                )
            else:
                subprocess.run(
                    ["git", "pull", "origin", info["branch"]],
                    cwd=str(repo_dir),
                    capture_output=True,
                    timeout=60
                )
            
            return True
            
        except Exception:
            return False
    
    def clone_repo(self, name: str) -> bool:
        """克隆仓库"""
        if name not in self.remotes:
            return False
        
        info = self.remotes[name]
        url = info["url"]
        
        if not url:
            return False
        
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", url, str(info["dir"])],
                capture_output=True,
                text=True,
                timeout=180
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有仓库状态"""
        status = {}
        
        for name, info in self.remotes.items():
            repo_dir = info["dir"]
            
            if not repo_dir.exists():
                status[name] = {"exists": False, "ahead": 0, "behind": 0}
                continue
            
            try:
                # 获取分支信息
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(repo_dir),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                branch = result.stdout.strip() if result.returncode == 0 else "unknown"
                
                # 获取远程差异
                result = subprocess.run(
                    ["git", "rev-list", "--left-right", "--count", 
                     f"HEAD...origin/{info['branch']}"],
                    cwd=str(repo_dir),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    ahead, behind = result.stdout.strip().split()
                else:
                    ahead, behind = 0, 0
                
                status[name] = {
                    "exists": True,
                    "branch": branch,
                    "ahead": int(ahead),
                    "behind": int(behind)
                }
                
            except Exception:
                status[name] = {"exists": False, "error": True}
        
        return status


# ============================================================================
# 主集成管理器
# ============================================================================

class OpenCodeIntegration:
    """OpenCode 完整集成管理器"""
    
    _instance: Optional["OpenCodeIntegration"] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config: Optional[OpenCodeConfig] = None):
        if self._initialized:
            return
        
        self._initialized = True
        self.config = config or OpenCodeConfig()
        self.cli = OpenCodeCLI()
        self.ohmy = OhMyOpenCodeManager()
        self.sync = EmbeddedRepoSync()
        self._status = OpenCodeStatus.STOPPED
        self._lock = threading.Lock()
    
    @property
    def status(self) -> OpenCodeStatus:
        """获取当前状态"""
        with self._lock:
            if self.cli.is_running:
                self._status = OpenCodeStatus.RUNNING
            return self._status
    
    def check_prerequisites(self) -> Dict[str, bool]:
        """检查前置条件"""
        return {
            "opencode_cli": self.cli.cli_path.exists() if hasattr(self.cli, 'cli_path') else False,
            "oh_my_opencode": self.ohmy.is_installed(),
            "git": self._check_git(),
            "bun_or_npm": self._check_bun_or_npm()
        }
    
    def _check_git(self) -> bool:
        """检查 Git"""
        try:
            subprocess.run(["git", "--version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False
    
    def _check_bun_or_npm(self) -> bool:
        """检查 Bun 或 NPM"""
        try:
            subprocess.run(["bun", "--version"], capture_output=True, timeout=5)
            return True
        except Exception:
            pass
        
        try:
            subprocess.run(["npm", "--version"], capture_output=True, timeout=5)
            return True
        except Exception:
            pass
        
        return False
    
    def setup(self, interactive: bool = True) -> bool:
        """初始化设置"""
        try:
            # 1. 同步嵌入式仓库
            print("📦 Syncing embedded repositories...")
            sync_results = self.sync.sync_all()
            
            for name, success in sync_results.items():
                status = "✅" if success else "❌"
                print(f"  {status} {name}")
            
            # 2. 构建 oh-my-opencode
            if self.ohmy.plugin_dir.exists() and not self.ohmy.is_installed():
                print("🔧 Building oh-my-opencode plugin...")
                if self.ohmy.build():
                    print("  ✅ Plugin built successfully")
                else:
                    print("  ⚠️ Plugin build failed, will try npm fallback")
            
            # 3. 配置
            if self.ohmy.is_installed():
                print("⚙️ Configuring OpenCode...")
                self.ohmy.configure(self.config.oh_my_opencode_config)
                print("  ✅ Configuration complete")
            
            # 4. 安装 OpenCode CLI (如果需要)
            if not self.cli.cli_path.exists():
                print("📥 Installing OpenCode CLI...")
                if self.cli.install():
                    print("  ✅ CLI installed")
                else:
                    print("  ⚠️ CLI install failed, trying PATH version")
            
            return True
            
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return False
    
    def sync_upstream(self, force: bool = False) -> Dict[str, bool]:
        """同步上游代码"""
        return self.sync.sync_all(force=force)
    
    def get_info(self) -> Dict[str, Any]:
        """获取完整信息"""
        return {
            "status": self.status.value,
            "prerequisites": self.check_prerequisites(),
            "sync_status": self.sync.status(),
            "cli_version": self.cli.version(),
            "plugins": self._list_plugins()
        }
    
    def _list_plugins(self) -> List[PluginInfo]:
        """列出已安装插件"""
        plugins = []
        
        if self.ohmy.is_installed():
            plugins.append(PluginInfo(
                name="oh-my-opencode",
                path=str(self.ohmy.dist_dir / "index.js"),
                enabled=True,
                description="OpenCode plugin collection with agents and tools"
            ))
        
        return plugins
    
    def install_plugin(self, plugin_path: str) -> bool:
        """安装额外插件"""
        try:
            config = self.ohmy.configure({"extra_plugin": plugin_path})
            return config
        except Exception:
            return False


# ============================================================================
# 便捷函数
# ============================================================================

def get_integration(config: Optional[OpenCodeConfig] = None) -> OpenCodeIntegration:
    """获取集成实例 (单例)"""
    return OpenCodeIntegration(config)


def quick_setup() -> bool:
    """快速设置"""
    integration = get_integration()
    return integration.setup()


# ============================================================================
# CLI 入口
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenCode Integration Manager")
    parser.add_argument("command", choices=["setup", "sync", "status", "info"],
                        help="Command to execute")
    parser.add_argument("--force", action="store_true", help="Force sync (hard reset)")
    parser.add_argument("--config", type=str, help="Config file path")
    
    args = parser.parse_args()
    integration = get_integration()
    
    if args.command == "setup":
        success = integration.setup()
        exit(0 if success else 1)
    
    elif args.command == "sync":
        results = integration.sync_upstream(force=args.force)
        for name, success in results.items():
            print(f"{'✅' if success else '❌'} {name}")
        exit(0 if all(results.values()) else 1)
    
    elif args.command == "status":
        info = integration.get_info()
        print(json.dumps(info, indent=2, default=str))
    
    elif args.command == "info":
        prereqs = integration.check_prerequisites()
        print("Prerequisites:")
        for name, ok in prereqs.items():
            print(f"  {'✅' if ok else '❌'} {name}")
