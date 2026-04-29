"""
OpenCode Core Bridge - 连接 LivingTree 与 OpenCode CLI
=======================================================

提供与 OpenCode CLI 的深度集成：
1. 进程生命周期管理
2. 消息管道通信
3. 嵌入式仓库同步
4. oh-my-opencode 插件集成

Author: LivingTreeAI
"""

import os
import sys
import json
import asyncio
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import queue
import io
import fcntl
import select

# ============================================================================
# 路径配置
# ============================================================================

# 尝试多种方式定位 libs 目录
def _find_libs_dir() -> Path:
    """查找 libs 目录"""
    # 1. 相对于当前文件
    current = Path(__file__).parent.parent.parent.parent / "libs"
    if current.exists():
        return current
    
    # 2. 相对于工作目录
    cwd = Path.cwd()
    libs = cwd / "libs"
    if libs.exists():
        return libs
    
    # 3. 尝试常见路径
    for parent in cwd.parents:
        libs = parent / "libs"
        if libs.exists():
            return libs
    
    # 4. 回退到硬编码路径
    return Path(__file__).parent.parent.parent.parent / "libs"

LIBS_DIR = _find_libs_dir()
OPENCODE_CORE_DIR = LIBS_DIR / "opencode-core"
OHMYOPENCODE_DIR = LIBS_DIR / "oh-my-opencode-plugin"
INTEGRATION_DIR = LIBS_DIR / "opencode_integration"


# ============================================================================
# 数据结构
# ============================================================================

class OpenCodeMode(Enum):
    """运行模式"""
    STANDALONE = "standalone"      # 独立 CLI 模式
    INTEGRATED = "integrated"     # 集成到 LivingTree
    EMBEDDED = "embedded"        # 嵌入式 IDE


@dataclass
class OpenCodeMessage:
    """消息结构"""
    type: str                    # user/assistant/system/tool
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OpenCodeSession:
    """会话信息"""
    session_id: str
    working_dir: Path
    started_at: float = field(default_factory=time.time)
    messages: List[OpenCodeMessage] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# 非阻塞流读取器
# ============================================================================

class NonBlockingReader:
    """非阻塞流读取器"""
    
    def __init__(self, stream: io.TextIOWrapper):
        self.stream = stream
        self._fd = stream.fileno()
        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """启动读取线程"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
    
    def _read_loop(self):
        """读取循环"""
        while self._running:
            try:
                # 使用 select 进行非阻塞读取
                ready, _, _ = select.select([self._fd], [], [], 0.1)
                
                if ready:
                    line = self.stream.readline()
                    if line:
                        self._queue.put(line)
                    elif self.stream.closed:
                        break
            except Exception:
                break
    
    def read(self, timeout: float = 0.1) -> Optional[str]:
        """读取一行"""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def read_all(self) -> List[str]:
        """读取所有可用行"""
        lines = []
        while True:
            line = self.read(timeout=0.01)
            if line is None:
                break
            lines.append(line)
        return lines
    
    def stop(self):
        """停止读取"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)


# ============================================================================
# OpenCode CLI 包装器
# ============================================================================

class OpenCodeCLIWrapper:
    """
    OpenCode CLI 包装器
    提供与 OpenCode CLI 的完整交互
    """
    
    def __init__(
        self,
        core_dir: Path = OPENCODE_CORE_DIR,
        work_dir: Optional[Path] = None
    ):
        self.core_dir = core_dir
        self.work_dir = work_dir or Path.cwd()
        self._process: Optional[subprocess.Popen] = None
        self._stdout_reader: Optional[NonBlockingReader] = None
        self._stderr_reader: Optional[NonBlockingReader] = None
        self._lock = threading.Lock()
        self._session: Optional[OpenCodeSession] = None
    
    @property
    def cli_path(self) -> Path:
        """获取 CLI 路径"""
        # 1. 检查本地编译
        local_bin = self.core_dir / "bin" / "opencode"
        if local_bin.exists():
            return local_bin
        
        # 2. 检查 PATH
        which = shutil.which("opencode") if shutil else None
        if which:
            return Path(which)
        
        # 3. 检查 install 脚本
        install = self.core_dir / "install"
        if install.exists():
            return install
        
        # 4. 尝试直接使用 opencode 命令
        return Path("opencode")
    
    @property
    def is_installed(self) -> bool:
        """检查是否已安装"""
        try:
            result = subprocess.run(
                [str(self.cli_path), "--version"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def install(self) -> bool:
        """安装 OpenCode"""
        try:
            result = subprocess.run(
                [str(self.cli_path), "-y"],
                capture_output=True,
                timeout=300,
                cwd=str(self.core_dir)
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def version(self) -> Optional[str]:
        """获取版本"""
        try:
            result = subprocess.run(
                ["opencode", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None
    
    def start(
        self,
        task: Optional[str] = None,
        on_output: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        启动 OpenCode 会话
        
        Args:
            task: 初始任务描述
            on_output: 输出回调
        """
        with self._lock:
            if self._process is not None:
                return True
            
            try:
                # 准备环境
                env = os.environ.copy()
                
                # 设置 oh-my-opencode 插件路径
                plugin_path = OHMYOPENCODE_DIR / "dist" / "index.js"
                if plugin_path.exists():
                    env["OPENCODE_PLUGIN"] = str(plugin_path)
                
                # 构建命令
                cmd = ["opencode"]
                if task:
                    cmd.extend(["--task", task])
                
                # 启动进程
                self._process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    cwd=str(self.work_dir),
                    text=True,
                    bufsize=1  # 行缓冲
                )
                
                # 启动非阻塞读取
                self._stdout_reader = NonBlockingReader(
                    self._process.stdout
                )
                self._stderr_reader = NonBlockingReader(
                    self._process.stderr
                )
                self._stdout_reader.start()
                self._stderr_reader.start()
                
                # 创建会话
                self._session = OpenCodeSession(
                    session_id=f"oc_{int(time.time())}",
                    working_dir=self.work_dir
                )
                
                # 启动输出监控
                if on_output:
                    def monitor():
                        while self._process and self._process.poll() is None:
                            for line in self._stdout_reader.read_all():
                                if line:
                                    on_output(line)
                            for line in self._stderr_reader.read_all():
                                if line:
                                    on_output(f"[stderr] {line}")
                            time.sleep(0.05)
                    
                    threading.Thread(target=monitor, daemon=True).start()
                
                return True
                
            except Exception as e:
                self._process = None
                raise RuntimeError(f"Failed to start OpenCode: {e}")
    
    def send(self, message: str) -> bool:
        """发送消息"""
        if self._process is None:
            return False
        
        try:
            self._process.stdin.write(message + "\n")
            self._process.stdin.flush()
            
            # 记录到会话
            if self._session:
                self._session.messages.append(OpenCodeMessage(
                    type="user",
                    content=message
                ))
            
            return True
        except Exception:
            return False
    
    def read_output(self, timeout: float = 1.0) -> List[str]:
        """读取输出"""
        if self._stdout_reader is None:
            return []
        
        lines = []
        end_time = time.time() + timeout
        
        while time.time() < end_time:
            line = self._stdout_reader.read(timeout=0.1)
            if line:
                lines.append(line)
            else:
                break
        
        return lines
    
    def stop(self) -> bool:
        """停止会话"""
        with self._lock:
            if self._process is None:
                return True
            
            try:
                # 发送退出信号
                try:
                    self._process.stdin.write("\x04")  # Ctrl+D
                    self._process.stdin.flush()
                except Exception:
                    pass
                
                # 等待进程结束
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                
            finally:
                if self._stdout_reader:
                    self._stdout_reader.stop()
                if self._stderr_reader:
                    self._stderr_reader.stop()
                self._process = None
                self._stdout_reader = None
                self._stderr_reader = None
                self._session = None
            
            return True
    
    @property
    def is_running(self) -> bool:
        """检查是否运行中"""
        return self._process is not None and self._process.poll() is None
    
    def get_session(self) -> Optional[OpenCodeSession]:
        """获取当前会话"""
        return self._session


# ============================================================================
# OpenCode 插件管理器
# ============================================================================

class OpenCodePluginManager:
    """
    OpenCode 插件管理器
    管理 oh-my-opencode 和其他插件
    """
    
    def __init__(self, plugin_dir: Path = OHMYOPENCODE_DIR):
        self.plugin_dir = plugin_dir
        self.dist_dir = plugin_dir / "dist"
        self.config_file = Path.home() / ".config" / "opencode" / "opencode.json"
    
    def is_oh_my_opencode_installed(self) -> bool:
        """检查 oh-my-opencode 是否安装"""
        index_js = self.dist_dir / "index.js"
        return index_js.exists()
    
    def build_oh_my_opencode(self) -> bool:
        """构建 oh-my-opencode"""
        if not self.plugin_dir.exists():
            return False
        
        try:
            # 尝试 Bun
            try:
                subprocess.run(
                    ["bun", "--version"],
                    capture_output=True,
                    timeout=10,
                    check=True
                )
                use_bun = True
            except (subprocess.CalledProcessError, FileNotFoundError):
                use_bun = False
            
            if use_bun:
                # Bun 构建
                subprocess.run(
                    ["bun", "install"],
                    cwd=str(self.plugin_dir),
                    timeout=120
                )
                result = subprocess.run(
                    ["bun", "run", "build"],
                    cwd=str(self.plugin_dir),
                    timeout=120
                )
            else:
                # NPM fallback
                subprocess.run(
                    ["npm", "install"],
                    cwd=str(self.plugin_dir),
                    timeout=120
                )
                result = subprocess.run(
                    ["npm", "run", "build"],
                    cwd=str(self.plugin_dir),
                    timeout=120
                )
            
            return result.returncode == 0 and self.is_oh_my_opencode_installed()
            
        except Exception:
            return False
    
    def configure(self) -> bool:
        """配置 OpenCode 使用插件"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        config = {}
        if self.config_file.exists():
            try:
                config = json.loads(self.config_file.read_text())
            except Exception:
                pass
        
        # 添加插件
        plugin_path = f"file://{self.dist_dir / 'index.js'}"
        if "plugin" not in config:
            config["plugin"] = []
        if isinstance(config["plugin"], list) and plugin_path not in config["plugin"]:
            config["plugin"].append(plugin_path)
        
        self.config_file.write_text(json.dumps(config, indent=2))
        return True
    
    def get_plugin_info(self) -> Dict[str, Any]:
        """获取插件信息"""
        return {
            "oh_my_opencode": {
                "installed": self.is_oh_my_opencode_installed(),
                "path": str(self.dist_dir / "index.js") if self.dist_dir.exists() else None,
                "source": str(self.plugin_dir)
            }
        }


# ============================================================================
# 嵌入式仓库同步器
# ============================================================================

class EmbeddedRepoSyncer:
    """
    嵌入式仓库同步器
    支持从上游拉取更新
    """
    
    def __init__(self, libs_dir: Path = LIBS_DIR):
        self.libs_dir = libs_dir
        self.repos = {
            "opencode-core": {
                "dir": libs_dir / "opencode-core",
                "remote": "origin",
                "branch": "main"
            },
            "oh-my-opencode": {
                "dir": libs_dir / "oh-my-opencode-plugin",
                "remote": "origin",
                "branch": "master"
            }
        }
    
    def sync(self, name: str, force: bool = False) -> bool:
        """同步指定仓库"""
        if name not in self.repos:
            return False
        
        repo = self.repos[name]
        if not repo["dir"].exists():
            return self.clone(name)
        
        try:
            if force:
                subprocess.run(
                    ["git", "reset", "--hard", f"{repo['remote']}/{repo['branch']}"],
                    cwd=str(repo["dir"]),
                    timeout=60
                )
            else:
                subprocess.run(
                    ["git", "pull", repo["remote"], repo["branch"]],
                    cwd=str(repo["dir"]),
                    timeout=60
                )
            return True
        except Exception:
            return False
    
    def clone(self, name: str) -> bool:
        """克隆仓库"""
        if name not in self.repos:
            return False
        
        repo = self.repos[name]
        remotes = {
            "opencode-core": "https://github.com/opencode-ai/opencode.git",
            "oh-my-opencode": "https://github.com/code-yeongyu/oh-my-opencode.git"
        }
        
        if name not in remotes:
            return False
        
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", 
                 remotes[name], str(repo["dir"])],
                timeout=180
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def sync_all(self, force: bool = False) -> Dict[str, bool]:
        """同步所有仓库"""
        results = {}
        for name in self.repos:
            results[name] = self.sync(name, force=force)
        return results
    
    def status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有仓库状态"""
        status = {}
        for name, repo in self.repos.items():
            if not repo["dir"].exists():
                status[name] = {"exists": False}
                continue
            
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(repo["dir"]),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                has_changes = bool(result.stdout.strip())
                
                status[name] = {
                    "exists": True,
                    "has_changes": has_changes
                }
            except Exception:
                status[name] = {"exists": False}
        
        return status


# ============================================================================
# 主控制器
# ============================================================================

class OpenCodeBridge:
    """
    OpenCode 桥接器
    整合所有功能的主控制器
    """
    
    _instance: Optional["OpenCodeBridge"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self):
        """初始化"""
        self.cli = OpenCodeCLIWrapper()
        self.plugins = OpenCodePluginManager()
        self.syncer = EmbeddedRepoSyncer()
        self._mode = OpenCodeMode.INTEGRATED
    
    @property
    def mode(self) -> OpenCodeMode:
        return self._mode
    
    @mode.setter
    def mode(self, value: OpenCodeMode):
        self._mode = value
    
    def check_status(self) -> Dict[str, Any]:
        """检查完整状态"""
        return {
            "cli_installed": self.cli.is_installed,
            "cli_version": self.cli.version(),
            "cli_running": self.cli.is_running,
            "oh_my_opencode": self.plugins.get_plugin_info(),
            "repos": self.syncer.status(),
            "mode": self._mode.value
        }
    
    def setup(self, interactive: bool = True) -> bool:
        """设置环境"""
        success = True
        
        # 1. 同步仓库
        if interactive:
            print("📦 Syncing embedded repositories...")
        sync_results = self.syncer.sync_all()
        for name, ok in sync_results.items():
            if interactive:
                print(f"  {'✅' if ok else '❌'} {name}")
            success = success and ok
        
        # 2. 构建 oh-my-opencode
        if self.plugins.plugin_dir.exists() and not self.plugins.is_oh_my_opencode_installed():
            if interactive:
                print("🔧 Building oh-my-opencode...")
            if self.plugins.build_oh_my_opencode():
                self.plugins.configure()
                if interactive:
                    print("  ✅ Plugin built and configured")
            else:
                if interactive:
                    print("  ⚠️ Plugin build failed (might need bun/npm)")
        
        # 3. 检查 OpenCode CLI
        if not self.cli.is_installed:
            if interactive:
                print("📥 Installing OpenCode CLI...")
            if self.cli.install():
                if interactive:
                    print("  ✅ CLI installed")
            else:
                if interactive:
                    print("  ⚠️ CLI install failed")
        
        return success
    
    def start_session(
        self,
        task: Optional[str] = None,
        on_output: Optional[Callable[[str], None]] = None
    ) -> bool:
        """启动会话"""
        return self.cli.start(task=task, on_output=on_output)
    
    def send_message(self, message: str) -> bool:
        """发送消息"""
        return self.cli.send(message)
    
    def stop_session(self) -> bool:
        """停止会话"""
        return self.cli.stop()
    
    def read_output(self, timeout: float = 1.0) -> List[str]:
        """读取输出"""
        return self.cli.read_output(timeout=timeout)


# ============================================================================
# 便捷函数
# ============================================================================

def get_bridge() -> OpenCodeBridge:
    """获取桥接器实例"""
    return OpenCodeBridge()


def quick_setup() -> bool:
    """快速设置"""
    return get_bridge().setup(interactive=True)


# ============================================================================
# 入口点
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenCode Bridge")
    parser.add_argument("cmd", choices=["setup", "sync", "status", "run"])
    parser.add_argument("--task", type=str, help="Task to run")
    parser.add_argument("--force", action="store_true", help="Force sync")
    
    args = parser.parse_args()
    bridge = get_bridge()
    
    if args.cmd == "setup":
        bridge.setup()
    elif args.cmd == "sync":
        results = bridge.syncer.sync_all(force=args.force)
        for name, ok in results.items():
            print(f"{'✅' if ok else '❌'} {name}")
    elif args.cmd == "status":
        import json
        print(json.dumps(bridge.check_status(), indent=2, default=str))
    elif args.cmd == "run":
        bridge.start_session(task=args.task)
        print("OpenCode session started. Type 'exit' to quit.")
        while True:
            try:
                msg = input("> ")
                if msg.lower() in ("exit", "quit"):
                    break
                bridge.send_message(msg)
                for line in bridge.read_output(timeout=2):
                    print(line.rstrip())
            except KeyboardInterrupt:
                break
        bridge.stop_session()
