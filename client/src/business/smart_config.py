"""
智能配置系统
Smart Configuration System

功能：
- 自动检测运行时环境
- 基于环境自动调整配置
- 由系统大脑驱动的自我优化
- 配置版本管理和回滚
"""

import os
import json
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import platform
import psutil

from PyQt6.QtCore import QTimer


class Environment(Enum):
    """运行环境类型"""
    UNKNOWN = "unknown"
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    WSL = "wsl"  # Windows Subsystem for Linux
    DOCKER = "docker"


class Profile(Enum):
    """配置方案"""
    DEFAULT = "default"
    HIGH_PERFORMANCE = "high_performance"
    LOW_MEMORY = "low_memory"
    PORTABLE = "portable"  # 便携模式


@dataclass
class RuntimeEnvironment:
    """运行时环境信息"""
    environment: Environment = Environment.UNKNOWN
    os_type: str = ""
    os_version: str = ""
    cpu_count: int = 0
    cpu_brand: str = ""
    memory_total: int = 0  # bytes
    memory_available: int = 0  # bytes
    gpu_available: bool = False
    gpu_memory: int = 0  # bytes
    is_wsl: bool = False
    is_docker: bool = False
    is_portable: bool = False
    disk_free_space: int = 0  # bytes
    network_type: str = "unknown"  # ethernet, wifi, unknown
    python_version: str = ""
    python_arch: str = ""  # x86_64, arm64, etc.

    # 性能指标
    cpu_usage: float = 0.0
    memory_usage: float = 0.0


@dataclass
class OptimizationSuggestion:
    """优化建议"""
    category: str  # 配置类别
    key: str  # 配置键
    current_value: Any
    suggested_value: Any
    reason: str
    priority: int = 0  # 优先级，越高越重要


@dataclass
class ConfigProfile:
    """配置方案"""
    name: str
    description: str
    ollama_num_ctx: int = 8192
    ollama_num_gpu: int = 0
    ollama_keep_alive: str = "5m"
    agent_max_iterations: int = 90
    agent_max_tokens: int = 4096
    agent_temperature: float = 0.7
    max_concurrent_tasks: int = 3
    enable_streaming: bool = True
    cache_size_mb: int = 500
    model_preload: bool = True


# 默认配置方案
DEFAULT_PROFILES = {
    Profile.DEFAULT: ConfigProfile(
        name="default",
        description="默认配置，平衡性能和资源使用",
        ollama_num_ctx=8192,
        ollama_num_gpu=0,
        agent_max_iterations=90,
        agent_max_tokens=4096,
        max_concurrent_tasks=3,
    ),
    Profile.HIGH_PERFORMANCE: ConfigProfile(
        name="high_performance",
        description="高性能配置，适合高配机器",
        ollama_num_ctx=16384,
        ollama_num_gpu=-1,  # 全部GPU
        ollama_keep_alive="30m",
        agent_max_iterations=150,
        agent_max_tokens=8192,
        max_concurrent_tasks=5,
        model_preload=True,
    ),
    Profile.LOW_MEMORY: ConfigProfile(
        name="low_memory",
        description="低内存配置，适合老机器",
        ollama_num_ctx=4096,
        ollama_num_gpu=0,
        ollama_keep_alive="2m",
        agent_max_iterations=50,
        agent_max_tokens=2048,
        max_concurrent_tasks=1,
        enable_streaming=True,
        cache_size_mb=200,
        model_preload=False,
    ),
    Profile.PORTABLE: ConfigProfile(
        name="portable",
        description="便携模式配置",
        ollama_num_ctx=8192,
        ollama_num_gpu=0,
        ollama_keep_alive="5m",
        agent_max_iterations=90,
        agent_max_tokens=4096,
        max_concurrent_tasks=2,
        model_preload=False,
    ),
}


@dataclass
class ConfigHistory:
    """配置历史记录"""
    timestamp: float
    action: str  # "set", "optimize", "profile_change"
    key: str
    old_value: Any
    new_value: Any
    reason: str = ""


class EnvironmentDetector:
    """
    运行时环境检测器

    检测系统环境、硬件配置等信息
    """

    @staticmethod
    def detect() -> RuntimeEnvironment:
        """检测运行环境"""
        env = RuntimeEnvironment()

        # OS信息
        env.os_type = platform.system().lower()
        if env.os_type == "windows":
            env.environment = Environment.WINDOWS
            try:
                import wmi
                c = wmi.WMI()
                for os_obj in c.Win32_OperatingSystem():
                    env.os_version = os_obj.Caption
            except ImportError:
                env.os_version = platform.version()
        elif env.os_type == "linux":
            env.environment = Environment.LINUX
            env.os_version = platform.version()

            # 检测WSL
            if os.path.exists("/proc/version"):
                with open("/proc/version") as f:
                    content = f.read().lower()
                    if "microsoft" in content or "wsl" in content:
                        env.is_wsl = True
                        env.environment = Environment.WSL

            # 检测Docker
            if os.path.exists("/.dockerenv"):
                env.is_docker = True
                env.environment = Environment.DOCKER
        elif env.os_type == "darwin":
            env.environment = Environment.MACOS
            env.os_version = platform.mac_ver()[0]

        # CPU信息
        env.cpu_count = os.cpu_count() or 1
        try:
            env.cpu_brand = platform.processor()
            if not env.cpu_brand:
                import subprocess
                result = subprocess.run(
                    ["cat", "/proc/cpuinfo"],
                    capture_output=True, text=True
                )
                for line in result.stdout.split("\n"):
                    if line.startswith("model name"):
                        env.cpu_brand = line.split(":")[1].strip()
                        break
        except Exception:
            env.cpu_brand = "Unknown"

        # 内存信息
        try:
            mem = psutil.virtual_memory()
            env.memory_total = mem.total
            env.memory_available = mem.available
            env.memory_usage = mem.percent / 100.0
        except Exception:
            env.memory_total = 8 * 1024**3  # 默认8GB
            env.memory_available = 4 * 1024**3

        # 磁盘空间
        try:
            disk = psutil.disk_usage("/")
            env.disk_free_space = disk.free
        except Exception:
            env.disk_free_space = 10 * 1024**3  # 默认10GB

        # GPU检测（简单检测）
        env.gpu_available = False
        try:
            import subprocess
            # Windows
            if env.os_type == "windows":
                result = subprocess.run(
                    ["wmic", "path", "win32_VideoController", "get", "name"],
                    capture_output=True, text=True
                )
                if result.stdout.strip():
                    env.gpu_available = True
            # Linux
            else:
                result = subprocess.run(
                    ["lspci"],
                    capture_output=True, text=True
                )
                if "VGA" in result.stdout or "NVIDIA" in result.stdout:
                    env.gpu_available = True
        except Exception:
            pass

        # Python信息
        env.python_version = platform.python_version()
        env.python_arch = platform.machine()

        # 便携模式检测
        env.is_portable = EnvironmentDetector._detect_portable()

        return env

    @staticmethod
    def _detect_portable() -> bool:
        """检测便携模式"""
        # 检查是否有便携标记文件
        script_dir = Path(__file__).parent.parent
        return (script_dir / "portable.txt").exists()


class SmartConfig:
    """
    智能配置管理器

    功能：
    1. 管理配置文件的读写
    2. 环境自动检测
    3. 基于环境自动选择配置方案
    4. 支持系统大脑驱动的自我优化
    5. 配置历史记录
    """

    def __init__(
        self,
        config_dir: str = None,
        use_brain: bool = True,
        brain=None
    ):
        """
        初始化智能配置管理器

        Args:
            config_dir: 配置目录
            use_brain: 是否使用系统大脑进行优化
            brain: 系统大脑实例
        """
        self.config_dir = Path(config_dir) if config_dir else self._get_config_dir()
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 系统大脑
        self.use_brain = use_brain
        self.brain = brain

        # 运行时环境
        self._runtime_env: Optional[RuntimeEnvironment] = None

        # 当前配置方案
        self._current_profile = Profile.DEFAULT

        # 配置数据
        self._config: Dict[str, Any] = {}

        # 配置历史
        self._history: List[ConfigHistory] = []

        # 优化建议
        self._suggestions: List[OptimizationSuggestion] = []

        # 回调
        self._optimization_callback: Optional[Callable] = None

        # 加载配置
        self._load_config()

        # 检测环境
        self.detect_environment()

    def _get_config_dir(self) -> Path:
        """获取配置目录"""
        # 优先用户目录
        user_dir = Path.home() / ".hermes-desktop"
        if os.access(str(Path.home()), os.W_OK):
            user_dir.mkdir(parents=True, exist_ok=True)
            return user_dir

        # 兜底到软件目录
        return Path(__file__).parent.parent / "config"

    def _get_config_path(self) -> Path:
        """获取配置文件路径"""
        return self.config_dir / "smart_config.json"

    def _get_history_path(self) -> Path:
        """获取历史记录路径"""
        return self.config_dir / "config_history.json"

    def detect_environment(self) -> RuntimeEnvironment:
        """检测运行环境"""
        self._runtime_env = EnvironmentDetector.detect()

        # 自动选择配置方案
        if not self._config.get("profile", ""):
            self._auto_select_profile()

        return self._runtime_env

    def _auto_select_profile(self):
        """自动选择配置方案"""
        env = self._runtime_env
        if not env:
            return

        # 便携模式
        if env.is_portable:
            self._current_profile = Profile.PORTABLE
            return

        # 低内存机器
        memory_gb = env.memory_total / (1024**3)
        if memory_gb < 4:
            self._current_profile = Profile.LOW_MEMORY
            return

        # 高性能机器（16GB+内存，多核CPU）
        if memory_gb >= 16 and env.cpu_count >= 4 and env.gpu_available:
            self._current_profile = Profile.HIGH_PERFORMANCE
            return

        # 默认
        self._current_profile = Profile.DEFAULT

    def _load_config(self):
        """加载配置"""
        path = self._get_config_path()

        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            except Exception:
                self._config = {}

        # 加载历史
        history_path = self._get_history_path()
        if history_path.exists():
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
                    self._history = [
                        ConfigHistory(**h) for h in history_data
                    ]
            except Exception:
                self._history = []

    def _save_config(self):
        """保存配置"""
        path = self._get_config_path()

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def _save_history(self):
        """保存历史记录"""
        path = self._get_history_path()

        # 只保留最近100条
        history_data = [
            asdict(h) for h in self._history[-100:]
        ]

        with open(path, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def set(self, key: str, value: Any, reason: str = ""):
        """设置配置值"""
        keys = key.split(".")
        config = self._config

        # 遍历到倒数第二层
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # 记录历史
        old_value = config.get(keys[-1])

        self._history.append(ConfigHistory(
            timestamp=time.time(),
            action="set",
            key=key,
            old_value=old_value,
            new_value=value,
            reason=reason
        ))

        # 设置新值
        config[keys[-1]] = value

        # 保存
        self._save_config()
        self._save_history()

    def get_profile(self) -> ConfigProfile:
        """获取当前配置方案"""
        profile_name = self._config.get("profile", "default")
        try:
            profile = Profile[profile_name.upper()]
        except KeyError:
            profile = Profile.DEFAULT

        return DEFAULT_PROFILES.get(profile, DEFAULT_PROFILES[Profile.DEFAULT])

    def set_profile(self, profile: Profile, reason: str = ""):
        """设置配置方案"""
        old_profile = self._current_profile

        self._history.append(ConfigHistory(
            timestamp=time.time(),
            action="profile_change",
            key="profile",
            old_value=old_profile.value,
            new_value=profile.value,
            reason=reason
        ))

        self._current_profile = profile
        self._config["profile"] = profile.value
        self._save_config()
        self._save_history()

    def get_runtime_environment(self) -> RuntimeEnvironment:
        """获取运行时环境"""
        if not self._runtime_env:
            self.detect_environment()
        return self._runtime_env

    def analyze_and_suggest(self) -> List[OptimizationSuggestion]:
        """
        分析并生成优化建议

        Returns:
            优化建议列表
        """
        suggestions = []
        env = self.get_runtime_environment()
        profile = self.get_profile()

        # 基于内存的建议
        memory_gb = env.memory_total / (1024**3)
        if memory_gb < 4:
            suggestions.append(OptimizationSuggestion(
                category="ollama",
                key="num_ctx",
                current_value=profile.ollama_num_ctx,
                suggested_value=4096,
                reason="内存低于4GB，建议减小上下文窗口",
                priority=3
            ))
        elif memory_gb >= 32:
            suggestions.append(OptimizationSuggestion(
                category="ollama",
                key="num_ctx",
                current_value=profile.ollama_num_ctx,
                suggested_value=16384,
                reason="内存充足，可以增大上下文窗口提升性能",
                priority=1
            ))

        # 基于GPU的建议
        if env.gpu_available:
            if profile.ollama_num_gpu == 0:
                suggestions.append(OptimizationSuggestion(
                    category="ollama",
                    key="num_gpu",
                    current_value=0,
                    suggested_value=-1,
                    reason="检测到GPU，建议开启GPU加速",
                    priority=2
                ))
        else:
            if profile.ollama_num_gpu != 0:
                suggestions.append(OptimizationSuggestion(
                    category="ollama",
                    key="num_gpu",
                    current_value=profile.ollama_num_gpu,
                    suggested_value=0,
                    reason="未检测到GPU，应关闭GPU加速",
                    priority=3
                ))

        # 基于WSL的建议
        if env.is_wsl:
            suggestions.append(OptimizationSuggestion(
                category="performance",
                key="batch_size",
                current_value=1,
                suggested_value=2,
                reason="WSL环境，建议增加批处理大小提升性能",
                priority=1
            ))

        self._suggestions = sorted(suggestions, key=lambda x: x.priority, reverse=True)
        return self._suggestions

    def optimize_with_brain(self, callback: Callable = None):
        """
        使用系统大脑进行智能优化

        Args:
            callback: 优化完成回调
        """
        if not self.use_brain or not self.brain:
            # 不使用大脑时，使用基础分析
            self.analyze_and_suggest()
            if callback:
                callback(self._suggestions)
            return

        def run_optimization():
            try:
                env = self.get_runtime_environment()
                suggestions = self.analyze_and_suggest()

                # 构建提示
                env_info = f"""
运行环境信息：
- 系统: {env.environment.value}
- CPU: {env.cpu_brand} ({env.cpu_count}核)
- 内存: {env.memory_total / (1024**3):.1f}GB (可用 {env.memory_available / (1024**3):.1f}GB)
- GPU: {'有' if env.gpu_available else '无'}
- 便携模式: {'是' if env.is_portable else '否'}

当前配置方案: {self._current_profile.value}
当前配置: {json.dumps(self._config, ensure_ascii=False)}

初步优化建议:
{chr(10).join([f"- {s.category}.{s.key}: {s.current_value} -> {s.suggested_value} ({s.reason})" for s in suggestions])}

请基于以上信息，给出更精细的配置优化建议，返回JSON格式。
"""

                # 调用大脑分析
                prompt = f"""你是一个系统配置优化专家。请分析以下运行环境信息，给出最佳配置建议。

{env_info}

请以JSON格式返回优化建议：
{{
    "analysis": "分析说明",
    "recommendations": [
        {{
            "category": "配置类别",
            "key": "配置键",
            "value": 建议值,
            "reason": "建议原因"
        }}
    ]
}}
"""

                result = self.brain.generate(prompt, max_tokens=1024)

                # 解析结果
                try:
                    import re
                    json_match = re.search(r'\{.*\}', result, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())

                        for rec in data.get("recommendations", []):
                            suggestions.append(OptimizationSuggestion(
                                category=rec.get("category", "general"),
                                key=rec.get("key", ""),
                                current_value=self.get(rec.get("key", "")),
                                suggested_value=rec.get("value"),
                                reason=rec.get("reason", ""),
                                priority=2
                            ))
                except Exception:
                    pass  # 使用基础分析结果

                self._suggestions = sorted(suggestions, key=lambda x: x.priority, reverse=True)

                if callback:
                    callback(self._suggestions)

            except Exception as e:
                if callback:
                    callback([])

        thread = threading.Thread(target=run_optimization, daemon=True)
        thread.start()

    def apply_suggestions(self, suggestions: List[OptimizationSuggestion] = None):
        """
        应用优化建议

        Args:
            suggestions: 要应用的建议，为空则应用所有建议
        """
        if suggestions is None:
            suggestions = self._suggestions

        for suggestion in suggestions:
            # 跳过可能不安全的更改
            if not self._is_safe_change(suggestion):
                continue

            self.set(
                f"{suggestion.category}.{suggestion.key}",
                suggestion.suggested_value,
                f"优化建议: {suggestion.reason}"
            )

    def _is_safe_change(self, suggestion: OptimizationSuggestion) -> bool:
        """检查更改是否安全"""
        # 禁止的更改
        forbidden = {
            "security.enable_auth": False,
            "security.admin_password": "***",
        }

        key = f"{suggestion.category}.{suggestion.key}"
        return key not in forbidden

    def rollback(self, steps: int = 1) -> bool:
        """
        回滚配置

        Args:
            steps: 回滚步数

        Returns:
            是否成功
        """
        if len(self._history) < steps:
            return False

        for _ in range(steps):
            history = self._history.pop()
            keys = history.key.split(".")

            config = self._config
            for k in keys[:-1]:
                if k not in config:
                    return False
                config = config[k]

            config[keys[-1]] = history.old_value

        self._save_config()
        self._save_history()
        return True

    def get_config_for_app(self) -> Dict[str, Any]:
        """
        获取用于应用程序的完整配置

        整合当前配置、配置方案和环境设置
        """
        profile = self.get_profile()
        env = self.get_runtime_environment()

        # 构建完整配置
        config = {
            # 基础配置
            "profile": self._current_profile.value,
            "environment": asdict(env),

            # Ollama配置
            "ollama": {
                "base_url": self.get("ollama.base_url", "http://localhost:11434"),
                "default_model": self.get("ollama.default_model", ""),
                "num_ctx": self.get("ollama.num_ctx", profile.ollama_num_ctx),
                "num_gpu": self.get("ollama.num_gpu", profile.ollama_num_gpu),
                "keep_alive": self.get("ollama.keep_alive", profile.ollama_keep_alive),
            },

            # Agent配置
            "agent": {
                "max_iterations": self.get("agent.max_iterations", profile.agent_max_iterations),
                "max_tokens": self.get("agent.max_tokens", profile.agent_max_tokens),
                "temperature": self.get("agent.temperature", profile.agent_temperature),
                "streaming": self.get("agent.streaming", profile.enable_streaming),
            },

            # 性能配置
            "performance": {
                "max_concurrent_tasks": self.get("performance.max_concurrent_tasks", profile.max_concurrent_tasks),
                "cache_size_mb": self.get("performance.cache_size_mb", profile.cache_size_mb),
                "model_preload": self.get("performance.model_preload", profile.model_preload),
            },

            # 窗口状态
            "window": {
                "width": self.get("window.width", 1400),
                "height": self.get("window.height", 900),
                "left_panel_width": self.get("window.left_panel_width", 240),
                "right_panel_width": self.get("window.right_panel_width", 300),
            },

            # 主题
            "theme": self.get("theme", "dark"),
        }

        return config

    def export_config(self, path: str = None) -> str:
        """
        导出配置

        Args:
            path: 导出路径

        Returns:
            导出文件路径
        """
        if not path:
            path = str(self.config_dir / f"config_export_{int(time.time())}.json")

        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "config": self._config,
                "history": [asdict(h) for h in self._history[-50:]],
                "export_time": time.time(),
                "environment": asdict(self._runtime_env) if self._runtime_env else None,
            }, f, ensure_ascii=False, indent=2)

        return path

    def import_config(self, path: str):
        """
        导入配置

        Args:
            path: 导入文件路径
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "config" in data:
            self._config = data["config"]
            self._save_config()

    def get_status(self) -> Dict[str, Any]:
        """获取配置状态"""
        env = self.get_runtime_environment()
        profile = self.get_profile()

        return {
            "profile": self._current_profile.value,
            "profile_description": profile.description,
            "environment": env.environment.value,
            "memory_gb": env.memory_total / (1024**3),
            "cpu_count": env.cpu_count,
            "gpu_available": env.gpu_available,
            "suggestions_count": len(self._suggestions),
            "history_count": len(self._history),
        }


# 单例
_smart_config: Optional[SmartConfig] = None


def get_smart_config(
    config_dir: str = None,
    use_brain: bool = True,
    brain=None
) -> SmartConfig:
    """获取智能配置管理器单例"""
    global _smart_config
    if _smart_config is None:
        _smart_config = SmartConfig(config_dir, use_brain, brain)
    return _smart_config


def init_smart_config_async(
    config_dir: str = None,
    use_brain: bool = True,
    brain=None,
    callback: Callable = None
) -> SmartConfig:
    """异步初始化智能配置"""
    config = get_smart_config(config_dir, use_brain, brain)

    def init():
        config.detect_environment()
        if callback:
            callback(config)

    thread = threading.Thread(target=init, daemon=True)
    thread.start()

    return config
