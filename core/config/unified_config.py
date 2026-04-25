"""
LivingTree AI Agent 统一配置管理模块
==========================================

支持:
- YAML 配置文件加载
- 环境变量自动替换 (${VAR_NAME})
- 配置热更新
- 分层配置合并 (default < config.yaml < 环境变量)
- 统一配置访问接口

使用示例:
    from core.config.unified_config import UnifiedConfig
    
    config = UnifiedConfig.get_instance()
    ollama_url = config.get("endpoints.ollama.url")
    timeout = config.get("timeouts.default", default=30)
"""

import os
import re
import yaml
import json
import logging
from pathlib import Path
from typing import Any, Optional, Dict, Union, List, TYPE_CHECKING
from dataclasses import dataclass, field, asdict
from threading import Lock
from copy import deepcopy
from enum import Enum
import platform
import psutil

logger = logging.getLogger("core.config.unified")

# 配置目录
CONFIG_DIR = Path.home() / ".livingtree"
CONFIG_FILE = CONFIG_DIR / "unified.yaml"
ENV_FILE = CONFIG_DIR / ".env"


class Environment(Enum):
    """运行环境类型"""
    UNKNOWN = "unknown"
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    WSL = "wsl"
    DOCKER = "docker"


class ConfigProfile(Enum):
    """配置方案"""
    AUTO = "auto"
    DEFAULT = "default"
    HIGH_PERFORMANCE = "high_performance"
    LOW_MEMORY = "low_memory"
    PORTABLE = "portable"


@dataclass
class RuntimeEnvironment:
    """运行时环境信息"""
    environment: str = "unknown"
    os_type: str = ""
    os_version: str = ""
    cpu_count: int = 0
    cpu_brand: str = ""
    memory_total: int = 0  # bytes
    memory_available: int = 0  # bytes
    memory_gb: float = 0.0
    gpu_available: bool = False
    gpu_memory: int = 0  # bytes
    is_wsl: bool = False
    is_docker: bool = False
    is_portable: bool = False
    disk_free_space: int = 0  # bytes
    network_type: str = "unknown"
    python_version: str = ""
    python_arch: str = ""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0


@dataclass
class ConfigSource:
    """配置来源"""
    name: str
    priority: int  # 越高优先级越高
    data: Dict[str, Any] = field(default_factory=dict)


class UnifiedConfig:
    """
    统一配置管理器 (单例模式)
    
    配置优先级: 默认值 < unified.yaml < 环境变量
    """
    
    _instance: Optional["UnifiedConfig"] = None
    _lock = Lock()
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._sources: list[ConfigSource] = []
        self._initialized = False
        self._hot_reload_enabled = False
        
        # 默认配置
        self._defaults: Dict[str, Any] = self._get_default_config()
    
    @classmethod
    def get_instance(cls) -> "UnifiedConfig":
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self) -> None:
        """初始化配置"""
        if self._initialized:
            return
        
        # 确保配置目录存在
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # 1. 加载默认配置
        self._sources.append(ConfigSource("defaults", 0, self._defaults))
        
        # 2. 加载 unified.yaml
        if CONFIG_FILE.exists():
            try:
                data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
                self._sources.append(ConfigSource("unified.yaml", 1, data))
                logger.info(f"加载配置文件: {CONFIG_FILE}")
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}")
        
        # 3. 合并配置
        self._merge_config()
        
        # 4. 应用环境变量替换
        self._apply_env_substitution()
        
        self._initialized = True
        self._runtime_env: Optional[RuntimeEnvironment] = None
        logger.info("统一配置管理器初始化完成")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            # ── 服务端点配置 ──
            "endpoints": {
                "ollama": {
                    "url": "http://localhost:11434",
                    "timeout": 30,
                    "max_retries": 3,
                },
                "cloud_sync": {
                    "url": "ws://localhost:8765/sync",
                    "timeout": 30,
                    "retry_delay": 5,
                },
                "tracker": {
                    "url": "http://localhost:8765",
                },
                "relay": {
                    "default": "139.199.124.242:8888",
                },
                "webrtc": {
                    "signaling": "0.0.0.0:8080",
                },
                "market": {
                    "tools": "https://market.hermes-ai.cn/tools/manifest.json",
                },
            },
            
            # ── 网络超时配置 ──
            "timeouts": {
                "default": 30,
                "long": 60,
                "browser": 15,
                "download": 120,
                "quick": 5,
                "search": 15,
                "llm_generate": 120,    # LLM generate 接口超时 (秒)
            },
            
            # ── 重试配置 ──
            "retries": {
                "default": 3,
                "message": 5,
                "download": 3,
                "exponential_base": 2,
            },
            
            # ── 延迟配置 (秒) ──
            "delays": {
                "polling_short": 0.1,
                "polling_medium": 0.5,
                "polling_long": 1.0,
                "polling_image": 2,    # Vheer 图像生成轮询间隔
                "polling_video": 3,    # Vheer 视频生成轮询间隔
                "periodic_check": 5,
                "heartbeat": 30,
                "long_task": 60,
                "wait_short": 1,
                "wait_medium": 2,
                "wait_long": 5,
                "wait_extreme": 10,
            },
            
            # ── Agent 配置 ──
            "agent": {
                "init_timeout": 10,      # 模型客户端初始化等待超时 (秒)
                "task_poll_interval": 0.1,  # 任务轮询间隔 (秒)
            },

            # ── 部署/沙箱配置 ──
            "deploy": {
                "step_delay": 0.5,       # 部署步骤间延迟 (秒)
                "verify_delay": 1.0,     # 验证阶段延迟 (秒)
                "rollback_delay": 0.5,   # 回滚步骤延迟 (秒)
                "sim_step_max": 1.0,     # 沙箱模拟单步最大耗时上限 (秒)
            },

            # ── Cloud Driver 配置 ──
            "cloud_driver": {
                "timeout": 120.0,             # 默认请求超时 (秒)
                "connect_timeout": 10.0,      # 连接超时 (秒)
                "max_retries": 2,             # 最大重试次数
                "retry_delay": 1.0,           # 重试基础延迟 (秒)
                "embed_timeout": 60.0,        # Embeddings 接口专用超时 (秒)
                "list_models_timeout": 5.0,   # 列出模型接口超时 (秒)
            },

            # ── P2P 模型分发配置 ──
            "p2p": {
                "broadcast_interval": 60,    # 模型广播间隔 (秒)
            },
            
            # ── Vheer API 配置 ──
            "vheer": {
                "timeout": 120,          # API 请求超时
                "download_timeout": 300,  # 下载超时
                "rate_limit_interval": 1.0,  # 速率限制间隔
            },
            
            # ── 中继/节点配置 ──
            "relay": {
                "heartbeat_interval": 30,     # 中继心跳间隔 (秒)
                "heartbeat_timeout": 60,      # 心跳超时 (秒)
                "connection_timeout": 30,      # 连接超时 (秒)
                "max_retries": 5,             # 最大重试次数
                # 连接状态机配置
                "health_check_interval": 5,    # 健康检查间隔 (秒)
                "degraded_recover_interval": 10,  # 降级恢复间隔 (秒)
                "offline_check_interval": 30,   # 离线检查间隔 (秒)
                "reconnect_wait": 5,           # 重连等待 (秒)
                "upgrade_check_interval": 60,   # 升级检查间隔 (秒)
                "nat_traverse_delay": 1,       # NAT穿透延迟 (秒)
                "stun_timeout": 5.0,           # STUN/TURN 请求超时
                "connection_poll_interval": 0.1,  # 连接轮询间隔 (秒)
                "thread_join_timeout": 2.0,    # 线程 join 超时 (秒)
                # 阶段超时
                "stage_timeout": {
                    "private_server": 5,
                    "public_signaling": 10,
                    "public_stun": 5,
                    "p2p_direct": 15,
                    "public_turn": 10,
                    "storage_relay": 30,
                },
                # 阶段最大重试
                "max_retries_per_stage": {
                    "private_server": 2,
                    "public_signaling": 3,
                    "public_stun": 2,
                    "p2p_direct": 1,
                    "public_turn": 2,
                    "storage_relay": 1,
                },
            },
            
            # ── 消息投递配置 ──
            "message": {
                "max_delivery_attempts": 3,    # 最大投递尝试次数
                "retry_base_delay": 5,         # 重试基础延迟 (秒)
            },
            
            # ── 轮询配置 ──
            "polling": {
                "image_max_wait": 120,   # 图像生成最大等待时间 (秒)
                "video_max_wait": 360,    # 视频生成最大等待时间 (秒)
            },
            
            # ── 批处理配置 ──
            "batch": {
                "default_size": 32,
                "large_size": 100,
                "small_size": 10,
                "page_size": 100,
            },
            
            # ── 资源限制 ──
            "limits": {
                "max_file_size": 52428800,  # 50MB
                "max_cache_size": 1073741824,  # 1GB
                "max_tokens": 2048,
                "max_context": 4096,
                "max_level": 4,
            },
            
            # ── API Keys (通过环境变量覆盖) ──
            "api_keys": {
                "openai": "${OPENAI_API_KEY}",
                "anthropic": "${ANTHROPIC_API_KEY}",
                "deepseek": "${DEEPSEEK_API_KEY}",
                "moonshot": "${MOONSHOT_API_KEY}",
                "dashscope": "${DASHSCOPE_API_KEY}",
                "modelscope": "${MODELSCOPE_TOKEN}",
                "huggingface": "${HF_TOKEN}",
            },
            
            # ── 路径配置 ──
            "paths": {
                "data": "./data",
                "logs": "./logs",
                "cache": "./cache",
                "temp": "/tmp",
                "distillation": "./data/distillation",
                "templates": "./data/templates",
                "vector_db": "./data/vector_db",
                "regulations": "./data/regulations",
            },
            
            # ── LLM 默认参数 ──
            "llm": {
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.1,
                "max_tokens": 2048,
            },
            
            # ── 密钥轮转配置 ──
            "key_rotation": {
                "check_interval": 3600,     # 检查间隔（秒），默认1小时
                "retry_delay": 300,         # 重试延迟（秒），默认5分钟
                "threshold_days": 30,       # 提前多少天开始轮转
                "notify_before_days": 7,   # 提前多少天通知
            },
            
            # ── 密钥健康监控配置 ──
            "key_health": {
                "interval": 3600,           # 监控间隔（秒），默认1小时
                "max_history": 100,         # 历史记录最大数量
                "expiry_warning_days": 7,   # 过期前警告天数
                "expiry_critical_days": 3,  # 过期前严重警告天数
            },
            
            # ── UI 自动化配置 ──
            "ui_automation": {
                "ui_max_tokens": 2048,      # UI分析时的最大Token数
                "parse_max_tokens": 512,    # 操作解析时的最大Token数
                "wait_timeout": 10.0,       # 等待元素超时（秒）
                "poll_interval": 0.5,       # 元素轮询间隔（秒）
                "type_interval": 0.1,       # 输入字符间隔（秒）
                "workflow_step_delay": 0.3, # 工作流步骤间延迟（秒）
            },
            
            # ── 异步任务队列配置 ──
            "task_queue": {
                "max_workers": 2,           # 最大并发数
                "debounce_delay": 3.0,      # 防抖延迟（秒）
                "default_debounce": 3.0,    # 默认防抖延迟（秒）
                "pause_timeout": 5.0,       # 暂停等待超时（秒）
                "task_timeout": 30,         # 任务执行超时（秒）
            },
            
            # ── 进化调度配置 ──
            "evolution": {
                "idle_minutes": 5,          # 空闲触发分钟数
                "check_interval": 30,        # 空闲检查间隔（秒）
                "thread_join_timeout": 2.0,   # 线程 join 超时（秒）
                "retry_delay": 1,            # 重试延迟基数（秒）
                "report_interval": 0.5,      # 上报间隔（秒）
            },
            
            # ── P2P 网络配置 ──
            "p2p_network": {
                "status_print_interval": 10,      # 状态打印间隔（秒）
                "topology_push_interval": 30,    # 拓扑推送间隔（秒）
                "health_check_interval": 30,     # P2P健康检查间隔（秒）
                "gossip_interval": 5,             # Gossip协议间隔（秒）
                "sync_interval": 30,              # 完整同步间隔（秒）
            },

            # ── 浏览器自动化配置 ──
            "browser_automation": {
                "clipboard_poll_interval": 1,      # 剪贴板轮询间隔（秒）
                "keyboard_poll_interval": 1,      # 键盘监听轮询间隔（秒）
                "error_recovery_delay": 5,        # 错误恢复延迟（秒）
                "default_wait_seconds": 3,         # 默认等待秒数
                "browser_startup_delay": 2,        # 浏览器启动延迟（秒）
                "click_delay": 0.5,               # 点击操作延迟（秒）
            },
            
            # ── Decommence 电商配置 ──
            "decommerce": {
                "discovery_timeout": 5,             # AI能力发现超时（秒）
                "ffmpeg_process_timeout": 5,         # FFmpeg进程超时（秒）
                "logistics_api_timeout": 10,         # 物流API超时（秒）
            },
            
            # ── Server 服务端配置 ──
            "server": {
                "gossip_interval": 2.0,            # Gossip传播间隔（秒）
                "ws_ping_interval": 30,            # WebSocket心跳间隔（秒）
                "ws_ping_timeout": 60,             # WebSocket心跳超时（秒）
                "credit_sync_interval": 30,        # 积分同步间隔（秒）
                "credit_api_timeout": 30.0,       # 积分API超时（秒）
            },
            
            # ── Smart Writing 智能写作配置 ──
            "smart_writing": {
                "default_timeout": 60,            # 代码执行默认超时（秒）
            },
            
            # ── 佣金系统配置 ──
            "commission": {
                "enabled": True,
                "modules": {
                    "deep_search": {"enabled": True, "rate": 0.3},
                    "creation": {"enabled": True, "rate": 0.2},
                    "stock_futures": {"enabled": True, "rate": 0.25},
                    "expert_training": {"enabled": True, "rate": 0.15},
                    "smart_writing": {"enabled": True, "rate": 0.2},
                    "expert_distillation": {"enabled": True, "rate": 0.25},
                },
                "payment": {
                    "wechat": {"enabled": True, "min_withdraw": 10},
                    "alipay": {"enabled": True, "min_withdraw": 10},
                },
                "settlement": {
                    "auto": False,           # 自动结算
                    "cycle": "monthly",      # 结算周期: daily/weekly/monthly
                    "threshold": 100,        # 最低提现门槛
                },
                "refund": {
                    "enabled": True,
                    "window_hours": 24,     # 退款窗口期（小时）
                },
            },
            
            # ── 去中心化知识系统配置 ──
            "decentralized": {
                "enabled": True,
                "p2p": {
                    "bootstrap_nodes": [],   # 引导节点列表
                    "port": 9001,            # P2P监听端口
                    "max_peers": 50,         # 最大连接节点数
                },
                "relay": {
                    "servers": ["139.199.124.242:8888"],
                    "fallback_enabled": True,
                },
                "knowledge_sync": {
                    "enabled": True,
                    "interval": 300,         # 同步间隔（秒）
                    "max_size_mb": 100,      # 最大同步大小（MB）
                },
                "tencent_cloud": {
                    "enabled": False,
                    "secret_id": "${TENCENT_SECRET_ID}",
                    "secret_key": "${TENCENT_SECRET_KEY}",
                    "bucket": "",
                    "region": "ap-guangzhou",
                },
                "collaboration": {
                    "enabled": True,
                    "conflict_resolution": "last_write_wins",  # 冲突解决策略
                },
            },
            
            # ── 模型 Provider 槽位配置 ──
            "provider": {
                "enabled": True,
                "slots": {
                    "slot_1": {
                        "name": "primary",
                        "provider": "openai",
                        "model": "gpt-4",
                        "fallback": "gpt-3.5-turbo",
                        "priority": 1,
                    },
                    "slot_2": {
                        "name": "secondary",
                        "provider": "anthropic",
                        "model": "claude-3-sonnet",
                        "fallback": "claude-3-haiku",
                        "priority": 2,
                    },
                    "slot_3": {
                        "name": "local",
                        "provider": "ollama",
                        "model": "llama3",
                        "fallback": "mistral",
                        "priority": 3,
                    },
                },
                "strategy": {
                    "mode": "failover",      # failover/load_balance/priority
                    "health_check_interval": 60,
                    "auto_switch": True,
                },
                "ab_test": {
                    "enabled": False,
                    "groups": {},            # A/B测试分组配置
                },
            },
            
            # ── 邮件通知配置 ──
            "email": {
                "enabled": False,
                "smtp": {
                    "host": "smtp.gmail.com",
                    "port": 587,
                    "use_tls": True,
                    "username": "${EMAIL_USERNAME}",
                    "password": "${EMAIL_PASSWORD}",
                },
                "sender": {
                    "name": "LivingTree AI",
                    "address": "${EMAIL_SENDER}",
                },
                "notification": {
                    "task_complete": True,
                    "error_alert": True,
                    "daily_summary": False,
                },
            },
            
            # ── 浏览器网关配置 ──
            "browser_gateway": {
                "enabled": True,
                "browser": {
                    "type": "chrome",        # chrome/firefox/edge
                    "headless": False,
                    "user_data_dir": None,   # 使用默认
                },
                "proxy": {
                    "enabled": False,
                    "type": "http",          # http/socks5
                    "host": "",
                    "port": 0,
                },
                "navigation": {
                    "timeout": 30,
                    "wait_for_load": True,
                },
            },
            
            # ── 安全/密钥管理配置 ──
            "security": {
                # 密钥轮转配置
                "key_rotation": {
                    "enabled": True,
                    "threshold_days": 30,              # 提前多少天开始轮转
                    "retry_delay": 300,                # 重试间隔（秒）
                    "notify_before_days": 7,           # 提前多少天通知
                    "auto_rotate": True,              # 是否自动轮转
                },
                # 密钥健康监控配置
                "key_health": {
                    "interval": 3600,                   # 监控检查间隔（秒）
                    "monitor_interval": 3600,          # 监控检查间隔（秒）- 别名
                    "health_check_timeout": 10,        # 健康检查超时（秒）
                    "critical_threshold": 7,           # 严重警告阈值（天数）
                    "warning_threshold": 30,          # 警告阈值（天数）
                },
                # API 密钥配置
                "api_keys": {
                    "request_timeout": 5,              # API 请求超时（秒）
                    "inject_timeout": 2,              # 密钥注入超时（秒）
                    "metadata_timeout": 1,            # 元数据服务超时（秒）
                },
                # 密钥存储配置
                "storage": {
                    "encrypted": True,                # 是否加密存储
                    "backup_enabled": True,           # 是否启用备份
                    "backup_interval": 86400,         # 备份间隔（秒）
                },
            },
            
            # ── Smart Config 智能配置 ──
            "smart_config": {
                "profile": "auto",             # auto/default/high_performance/low_memory/portable
                "auto_detect": True,           # 自动检测环境
                "auto_optimize": False,        # 自动应用优化建议
                "environment": {
                    "detected": False,
                    "os_type": "",
                    "memory_gb": 0,
                    "cpu_count": 0,
                    "gpu_available": False,
                    "is_portable": False,
                },
                "profiles": {
                    "default": {
                        "ollama_num_ctx": 8192,
                        "ollama_num_gpu": 0,
                        "agent_max_iterations": 90,
                        "agent_max_tokens": 4096,
                        "max_concurrent_tasks": 3,
                    },
                    "high_performance": {
                        "ollama_num_ctx": 16384,
                        "ollama_num_gpu": -1,
                        "agent_max_iterations": 150,
                        "agent_max_tokens": 8192,
                        "max_concurrent_tasks": 5,
                    },
                    "low_memory": {
                        "ollama_num_ctx": 4096,
                        "ollama_num_gpu": 0,
                        "agent_max_iterations": 50,
                        "agent_max_tokens": 2048,
                        "max_concurrent_tasks": 1,
                    },
                    "portable": {
                        "ollama_num_ctx": 8192,
                        "ollama_num_gpu": 0,
                        "agent_max_iterations": 90,
                        "agent_max_tokens": 4096,
                        "max_concurrent_tasks": 2,
                    },
                },
            },
        }
    
    def _merge_config(self) -> None:
        """合并所有配置源"""
        # 按优先级从低到高合并
        sorted_sources = sorted(self._sources, key=lambda s: s.priority)
        
        self._config = {}
        for source in sorted_sources:
            self._config = self._deep_merge(self._config, source.data)
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """深度合并两个字典"""
        result = deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result
    
    def _apply_env_substitution(self) -> None:
        """应用环境变量替换 ${VAR_NAME}"""
        self._config = self._substitute_env(self._config)
    
    def _substitute_env(self, obj: Any) -> Any:
        """递归替换环境变量"""
        if isinstance(obj, dict):
            return {k: self._substitute_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env(item) for item in obj]
        elif isinstance(obj, str):
            return self._substitute_string(obj)
        return obj
    
    def _substitute_string(self, value: str) -> str:
        """替换字符串中的环境变量 ${VAR_NAME}"""
        if not isinstance(value, str):
            return value
        
        # 匹配 ${VAR_NAME} 格式
        pattern = r'\$\{([^}]+)\}'
        
        def replacer(match):
            var_name = match.group(1)
            # 1. 先从环境变量获取
            env_value = os.environ.get(var_name)
            if env_value:
                return env_value
            # 2. 从 .env 文件获取
            env_value = self._get_env_from_file(var_name)
            if env_value:
                return env_value
            # 3. 保持原样
            return match.group(0)
        
        return re.sub(pattern, replacer, value)
    
    def _get_env_from_file(self, key: str) -> Optional[str]:
        """从 .env 文件获取环境变量"""
        if not ENV_FILE.exists():
            return None
        
        try:
            content = ENV_FILE.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    if k.strip() == key:
                        return v.strip().strip('"').strip("'")
        except Exception as e:
            logger.warning(f"读取 .env 文件失败: {e}")
        
        return None
    
    # ── 公开 API ───────────────────────────────────────────────────────
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值 (自动替换环境变量)
        
        Args:
            key: 配置键，支持点号分隔 (如 "endpoints.ollama.url")
            default: 默认值
        
        Returns:
            配置值或默认值 (字符串会自动替换 ${VAR_NAME})
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        # 字符串自动替换环境变量
        if isinstance(value, str):
            value = self._substitute_string(value)
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        设置配置值 (运行时生效，不持久化)
        
        Args:
            key: 配置键，支持点号分隔
            value: 配置值
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        logger.debug(f"设置配置: {key} = {value}")
    
    def get_ollama_url(self) -> str:
        """获取 Ollama 服务地址"""
        return self.get("endpoints.ollama.url", "http://localhost:11434")
    
    def get_ollama_timeout(self) -> int:
        """获取 Ollama 超时时间"""
        return self.get("endpoints.ollama.timeout", 30)
    
    def get_timeout(self, name: str = "default") -> int:
        """
        获取超时配置
        
        Args:
            name: 超时类型 (default/long/browser/download/quick/search)
        """
        return self.get(f"timeouts.{name}", 30)
    
    def get_delay(self, name: str = "polling_medium") -> float:
        """
        获取延迟配置
        
        Args:
            name: 延迟类型 (polling_short/polling_medium/polling_long/...)
        """
        return self.get(f"delays.{name}", 0.5)
    
    def get_max_retries(self, category: str = "default") -> int:
        """
        获取重试次数配置
        
        Args:
            category: 重试类别 (default/http/file/cloud/sync)
        """
        return self.get(f"retries.{category}", 3)
    
    def get_retry_delay(self, category: str = "default") -> float:
        """
        获取重试延迟配置 (秒)
        
        Args:
            category: 延迟类别 (default/http/file/quick/exponential)
        """
        return self.get(f"retries.{category}_delay", 1.0)
    
    def get_retry_config(self, category: str = "default") -> Dict[str, Any]:
        """
        获取完整的重试配置
        
        Args:
            category: 重试类别 (default/http/file/cloud/sync)
        
        Returns:
            {"max_retries": int, "delay": float, "backoff": str}
        """
        return {
            "max_retries": self.get_max_retries(category),
            "delay": self.get_retry_delay(category),
            "backoff": self.get(f"retries.{category}_backoff", "exponential")
        }
    
    def get_path(self, name: str = "data") -> str:
        """获取路径配置"""
        return self.get(f"paths.{name}", "./data")
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """
        获取 API Key
        
        Args:
            provider: 提供商名称 (openai/anthropic/deepseek/...)
        """
        key = self.get(f"api_keys.{provider}")
        if key and key.startswith("${") and key.endswith("}"):
            return None  # 未设置
        return key
    
    def get_heartbeat_config(self, category: str = "default") -> Dict[str, Any]:
        """
        获取心跳配置
        
        Args:
            category: 心跳类别 (default/service/payment/stream)
        
        Returns:
            {"interval": float, "timeout": float}
        """
        return {
            "interval": self.get(f"heartbeat.{category}_interval", self.get(f"heartbeat.{category}.interval", 10.0)),
            "timeout": self.get(f"heartbeat.{category}_timeout", self.get(f"heartbeat.{category}.timeout", 30.0)),
        }
    
    def get_polling_config(self, category: str = "default") -> Dict[str, Any]:
        """
        获取轮询配置
        
        Args:
            category: 轮询类别 (default/sync/check/wait)
        
        Returns:
            {"interval": float, "max_wait": float}
        """
        return {
            "interval": self.get(f"polling.{category}_interval", self.get(f"polling.{category}.interval", 5.0)),
            "max_wait": self.get(f"polling.{category}_max_wait", self.get(f"polling.{category}.max_wait", 60.0)),
        }
    
    def get_sync_config(self) -> Dict[str, Any]:
        """
        获取同步配置
        
        Returns:
            {"interval": int, "batch_size": int, "timeout": int, "retry_count": int, "retry_delay": int}
        """
        return {
            "interval": self.get("sync.interval", 30),
            "batch_size": self.get("sync.batch_size", 100),
            "timeout": self.get("sync.timeout", 30),
            "retry_count": self.get_max_retries("sync"),
            "retry_delay": self.get("sync.retry_delay", 5),
        }
    
    def get_key_rotation_config(self) -> Dict[str, Any]:
        """
        获取密钥轮转配置
        
        Returns:
            密钥轮转配置字典
        """
        return {
            "check_interval": self.get("key_rotation.check_interval", 3600),
            "retry_delay": self.get("key_rotation.retry_delay", 300),
            "threshold_days": self.get("key_rotation.threshold_days", 30),
            "notify_before_days": self.get("key_rotation.notify_before_days", 7),
        }
    
    def get_key_health_config(self) -> Dict[str, Any]:
        """
        获取密钥健康监控配置
        
        Returns:
            密钥健康监控配置字典
        """
        return {
            "interval": self.get("key_health.interval", 3600),
            "max_history": self.get("key_health.max_history", 100),
            "expiry_warning_days": self.get("key_health.expiry_warning_days", 7),
            "expiry_critical_days": self.get("key_health.expiry_critical_days", 3),
        }
    
    def get_ui_automation_config(self) -> Dict[str, Any]:
        """
        获取UI自动化配置
        
        Returns:
            UI自动化配置字典
        """
        return {
            "ui_max_tokens": self.get("ui_automation.ui_max_tokens", 2048),
            "parse_max_tokens": self.get("ui_automation.parse_max_tokens", 512),
            "wait_timeout": self.get("ui_automation.wait_timeout", 10.0),
            "poll_interval": self.get("ui_automation.poll_interval", 0.5),
            "type_interval": self.get("ui_automation.type_interval", 0.1),
            "workflow_step_delay": self.get("ui_automation.workflow_step_delay", 0.3),
        }
    
    def get_task_queue_config(self) -> Dict[str, Any]:
        """
        获取异步任务队列配置
        
        Returns:
            异步任务队列配置字典
        """
        return {
            "max_workers": self.get("task_queue.max_workers", 2),
            "debounce_delay": self.get("task_queue.debounce_delay", 3.0),
            "default_debounce": self.get("task_queue.default_debounce", 3.0),
            "pause_timeout": self.get("task_queue.pause_timeout", 5.0),
            "task_timeout": self.get("task_queue.task_timeout", 30),
        }
    
    def get_evolution_config(self) -> Dict[str, Any]:
        """
        获取进化调度配置
        
        Returns:
            进化调度配置字典
        """
        return {
            "idle_minutes": self.get("evolution.idle_minutes", 5),
            "check_interval": self.get("evolution.check_interval", 30),
            "thread_join_timeout": self.get("evolution.thread_join_timeout", 2.0),
            "retry_delay": self.get("evolution.retry_delay", 1),
            "report_interval": self.get("evolution.report_interval", 0.5),
        }

    def get_browser_automation_config(self) -> Dict[str, Any]:
        """
        获取浏览器自动化配置
        
        Returns:
            浏览器自动化配置字典
        """
        return {
            "clipboard_poll_interval": self.get("browser_automation.clipboard_poll_interval", 1),
            "keyboard_poll_interval": self.get("browser_automation.keyboard_poll_interval", 1),
            "error_recovery_delay": self.get("browser_automation.error_recovery_delay", 5),
            "default_wait_seconds": self.get("browser_automation.default_wait_seconds", 3),
            "browser_startup_delay": self.get("browser_automation.browser_startup_delay", 2),
            "click_delay": self.get("browser_automation.click_delay", 0.5),
        }
    
    def get_commission_config(self, module: Optional[str] = None) -> Dict[str, Any]:
        """
        获取佣金系统配置
        
        Args:
            module: 可选，指定模块名称 (deep_search/creation/stock_futures/...)
        
        Returns:
            佣金配置字典或指定模块配置
        """
        if module:
            return self.get(f"commission.modules.{module}", {})
        return {
            "enabled": self.get("commission.enabled", True),
            "modules": self.get("commission.modules", {}),
            "payment": self.get("commission.payment", {}),
            "settlement": self.get("commission.settlement", {}),
            "refund": self.get("commission.refund", {}),
        }
    
    def get_decentralized_config(self) -> Dict[str, Any]:
        """
        获取去中心化知识系统配置
        
        Returns:
            去中心化配置字典
        """
        return {
            "enabled": self.get("decentralized.enabled", True),
            "p2p": self.get("decentralized.p2p", {}),
            "relay": self.get("decentralized.relay", {}),
            "knowledge_sync": self.get("decentralized.knowledge_sync", {}),
            "tencent_cloud": self.get("decentralized.tencent_cloud", {}),
            "collaboration": self.get("decentralized.collaboration", {}),
        }
    
    def get_provider_config(self, slot: Optional[str] = None) -> Dict[str, Any]:
        """
        获取模型Provider槽位配置
        
        Args:
            slot: 可选，指定槽位名称 (slot_1/slot_2/slot_3)
        
        Returns:
            Provider配置字典或指定槽位配置
        """
        if slot:
            return self.get(f"provider.slots.{slot}", {})
        return {
            "enabled": self.get("provider.enabled", True),
            "slots": self.get("provider.slots", {}),
            "strategy": self.get("provider.strategy", {}),
            "ab_test": self.get("provider.ab_test", {}),
        }
    
    def get_provider_slot_by_priority(self, priority: int) -> Optional[Dict[str, Any]]:
        """
        根据优先级获取可用的Provider槽位
        
        Args:
            priority: 优先级 (1=最高)
        
        Returns:
            可用的槽位配置或None
        """
        slots = self.get("provider.slots", {})
        for slot_key, slot_config in sorted(slots.items(), key=lambda x: x[1].get("priority", 99)):
            if slot_config.get("priority") == priority and slot_config.get("enabled", True):
                return slot_config
        return None
    
    def get_email_config(self) -> Dict[str, Any]:
        """
        获取邮件通知配置
        
        Returns:
            邮件配置字典
        """
        return {
            "enabled": self.get("email.enabled", False),
            "smtp": self.get("email.smtp", {}),
            "sender": self.get("email.sender", {}),
            "notification": self.get("email.notification", {}),
        }
    
    def get_browser_gateway_config(self) -> Dict[str, Any]:
        """
        获取浏览器网关配置
        
        Returns:
            浏览器网关配置字典
        """
        return {
            "enabled": self.get("browser_gateway.enabled", True),
            "browser": self.get("browser_gateway.browser", {}),
            "proxy": self.get("browser_gateway.proxy", {}),
            "navigation": self.get("browser_gateway.navigation", {}),
        }
    
    def get_security_config(self, category: str = None) -> Dict[str, Any]:
        """
        获取安全/密钥管理配置
        
        Args:
            category: 可选，指定配置类别 (key_rotation/key_health/api_keys/storage)
        
        Returns:
            安全配置字典或指定类别配置
        """
        if category:
            return self.get(f"security.{category}", {})
        
        return {
            "key_rotation": self.get("security.key_rotation", {}),
            "key_health": self.get("security.key_health", {}),
            "api_keys": self.get("security.api_keys", {}),
            "storage": self.get("security.storage", {}),
        }
    
    def get_key_rotation_config(self) -> Dict[str, Any]:
        """
        获取密钥轮转配置
        
        Returns:
            密钥轮转配置字典
        """
        return self.get("security.key_rotation", {})
    
    def get_key_health_config(self) -> Dict[str, Any]:
        """
        获取密钥健康监控配置
        
        Returns:
            密钥健康监控配置字典
        """
        return self.get("security.key_health", {})
    
    def get_api_key_timeout(self) -> int:
        """
        获取 API 密钥请求超时
        
        Returns:
            超时秒数
        """
        return self.get("security.api_keys.request_timeout", 5)
    
    # ── Smart Config 智能配置 API ──────────────────────────────────
    
    def get_smart_config_profile(self) -> str:
        """
        获取当前智能配置profile
        
        Returns:
            Profile名称 (auto/default/high_performance/low_memory/portable)
        """
        return self.get("smart_config.profile", "auto")
    
    def set_smart_config_profile(self, profile: str) -> None:
        """
        设置智能配置profile
        
        Args:
            profile: Profile名称 (default/high_performance/low_memory/portable)
        """
        self.set("smart_config.profile", profile)
        logger.info(f"Smart Config profile 已设置为: {profile}")
    
    def detect_runtime_environment(self) -> RuntimeEnvironment:
        """
        检测运行时环境
        
        Returns:
            RuntimeEnvironment: 运行时环境信息
        """
        if self._runtime_env:
            return self._runtime_env
        
        env = RuntimeEnvironment()
        
        # OS信息
        env.os_type = platform.system().lower()
        if env.os_type == "windows":
            env.environment = Environment.WINDOWS.value
            env.os_version = platform.version()
        elif env.os_type == "linux":
            env.environment = Environment.LINUX.value
            env.os_version = platform.version()
            # 检测WSL
            if Path("/proc/version").exists():
                try:
                    content = Path("/proc/version").read_text().lower()
                    if "microsoft" in content or "wsl" in content:
                        env.is_wsl = True
                        env.environment = Environment.WSL.value
                except Exception:
                    pass
            # 检测Docker
            if Path("/.dockerenv").exists():
                env.is_docker = True
                env.environment = Environment.DOCKER.value
        elif env.os_type == "darwin":
            env.environment = Environment.MACOS.value
            env.os_version = platform.mac_ver()[0] or ""
        
        # CPU信息
        env.cpu_count = os.cpu_count() or 1
        env.cpu_brand = platform.processor() or "Unknown"
        
        # 内存信息
        try:
            mem = psutil.virtual_memory()
            env.memory_total = mem.total
            env.memory_available = mem.available
            env.memory_usage = mem.percent / 100.0
            env.memory_gb = mem.total / (1024**3)
        except Exception:
            env.memory_total = 8 * 1024**3
            env.memory_available = 4 * 1024**3
            env.memory_gb = 8.0
        
        # 磁盘空间
        try:
            disk = psutil.disk_usage("/")
            env.disk_free_space = disk.free
        except Exception:
            env.disk_free_space = 10 * 1024**3
        
        # GPU检测
        env.gpu_available = self._detect_gpu()
        
        # 便携模式检测
        env.is_portable = self._detect_portable()
        
        # Python信息
        env.python_version = platform.python_version()
        env.python_arch = platform.machine()
        
        # 保存到配置
        self._runtime_env = env
        self.set("smart_config.environment", {
            "detected": True,
            "os_type": env.os_type,
            "memory_gb": env.memory_gb,
            "cpu_count": env.cpu_count,
            "gpu_available": env.gpu_available,
            "is_portable": env.is_portable,
        })
        
        logger.info(f"运行时环境检测完成: {env.environment}, {env.memory_gb:.1f}GB, {env.cpu_count}核")
        return env
    
    def _detect_gpu(self) -> bool:
        """检测GPU是否可用"""
        try:
            if platform.system().lower() == "windows":
                import subprocess
                result = subprocess.run(
                    ["wmic", "path", "win32_VideoController", "get", "name"],
                    capture_output=True, text=True
                )
                return bool(result.stdout.strip())
            else:
                return False
        except Exception:
            return False
    
    def _detect_portable(self) -> bool:
        """检测便携模式"""
        script_dir = Path(__file__).parent.parent
        return (script_dir / "portable.txt").exists()
    
    def get_recommended_profile(self) -> str:
        """
        根据运行时环境获取推荐配置profile
        
        Returns:
            推荐的Profile名称
        """
        env = self.detect_runtime_environment()
        
        # 便携模式
        if env.is_portable:
            return ConfigProfile.PORTABLE.value
        
        # 低内存机器 (<4GB)
        if env.memory_gb < 4:
            return ConfigProfile.LOW_MEMORY.value
        
        # 高性能机器 (16GB+内存，多核CPU，有GPU)
        if env.memory_gb >= 16 and env.cpu_count >= 4 and env.gpu_available:
            return ConfigProfile.HIGH_PERFORMANCE.value
        
        # 默认
        return ConfigProfile.DEFAULT.value
    
    def get_profile_config(self, profile: str = None) -> Dict[str, Any]:
        """
        获取指定profile的配置
        
        Args:
            profile: Profile名称，为空则获取当前profile
        
        Returns:
            Profile配置字典
        """
        if profile is None:
            profile = self.get_smart_config_profile()
        
        # 如果是auto，使用推荐profile
        if profile == "auto":
            profile = self.get_recommended_profile()
        
        return self.get(f"smart_config.profiles.{profile}", self.get("smart_config.profiles.default", {}))
    
    def apply_profile(self, profile: str = None) -> Dict[str, Any]:
        """
        应用配置profile
        
        Args:
            profile: Profile名称，为空则使用推荐的profile
        
        Returns:
            应用后的配置
        """
        if profile is None or profile == "auto":
            profile = self.get_recommended_profile()
        
        self.set("smart_config.profile", profile)
        profile_config = self.get_profile_config(profile)
        
        logger.info(f"已应用配置profile: {profile}")
        return profile_config
    
    def get_runtime_environment(self) -> RuntimeEnvironment:
        """
        获取运行时环境（懒加载）
        
        Returns:
            RuntimeEnvironment: 运行时环境信息
        """
        if not self._runtime_env:
            return self.detect_runtime_environment()
        return self._runtime_env
    
    def reload(self) -> None:
        """重新加载配置"""
        logger.info("重新加载配置...")
        self._sources = []
        self._defaults = self._get_default_config()
        self._initialize()
    
    def export(self) -> Dict[str, Any]:
        """导出当前配置"""
        return deepcopy(self._config)
    
    def to_yaml(self) -> str:
        """导出为 YAML 格式"""
        return yaml.dump(self._config, allow_unicode=True, default_flow_style=False)
    
    def save(self, path: Optional[Path] = None) -> None:
        """
        保存配置到文件
        
        Args:
            path: 保存路径，默认为 unified.yaml
        """
        save_path = path or CONFIG_FILE
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(self.to_yaml(), encoding="utf-8")
        logger.info(f"配置已保存: {save_path}")
    
    def import_config(
        self,
        path: Optional[Path] = None,
        strategy: str = "merge",  # merge | replace | validate
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        从文件导入配置
        
        Args:
            path: 导入文件路径
            strategy: 合并策略
                - merge: 合并到现有配置（默认）
                - replace: 替换整个配置
                - validate: 仅验证，不导入
            validate: 是否验证配置结构
        
        Returns:
            导入的配置字典
        """
        import_path = path or CONFIG_FILE
        
        if not import_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {import_path}")
        
        # 根据扩展名判断格式
        suffix = import_path.suffix.lower()
        if suffix in [".yaml", ".yml"]:
            config_data = yaml.safe_load(import_path.read_text(encoding="utf-8")) or {}
        elif suffix == ".json":
            config_data = json.loads(import_path.read_text(encoding="utf-8"))
        else:
            # 尝试自动检测格式
            content = import_path.read_text(encoding="utf-8").strip()
            if content.startswith("{") or content.startswith("["):
                config_data = json.loads(content)
            else:
                config_data = yaml.safe_load(content) or {}
        
        # 验证配置结构
        if validate:
            self._validate_import_config(config_data)
        
        # 根据策略应用配置
        if strategy == "replace":
            self._config = config_data
            logger.info(f"配置已替换: {import_path}")
        elif strategy == "merge":
            self._config = self._deep_merge(self._config, config_data)
            logger.info(f"配置已合并: {import_path}")
        elif strategy == "validate":
            logger.info(f"配置验证通过: {import_path}")
        else:
            raise ValueError(f"未知的合并策略: {strategy}")
        
        return config_data
    
    def _validate_import_config(self, config: Dict[str, Any]) -> None:
        """
        验证导入的配置结构
        
        Args:
            config: 要验证的配置字典
        
        Raises:
            ValueError: 配置结构无效
        """
        if not isinstance(config, dict):
            raise ValueError("配置必须是字典类型")
        
        # 检查必需的顶级键
        required_keys = ["endpoints", "timeouts"]
        for key in required_keys:
            if key not in config:
                logger.warning(f"建议包含顶级键: {key}")
        
        # 检查数据类型
        invalid_keys = []
        for key, value in config.items():
            if isinstance(value, dict):
                continue
            if not isinstance(value, (str, int, float, bool, list, type(None))):
                invalid_keys.append(key)
        
        if invalid_keys:
            logger.warning(f"以下键的值类型可能不兼容: {invalid_keys}")
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        深度合并两个配置字典
        
        Args:
            base: 基础配置
            override: 覆盖配置
        
        Returns:
            合并后的配置
        """
        result = deepcopy(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        
        return result
    
    def from_yaml(self, yaml_content: str, strategy: str = "merge") -> Dict[str, Any]:
        """
        从 YAML 字符串导入配置
        
        Args:
            yaml_content: YAML 格式的配置字符串
            strategy: 合并策略
        
        Returns:
            导入的配置字典
        """
        config_data = yaml.safe_load(yaml_content) or {}
        return self.import_config_str(config_data, strategy)
    
    def from_json(self, json_content: str, strategy: str = "merge") -> Dict[str, Any]:
        """
        从 JSON 字符串导入配置
        
        Args:
            json_content: JSON 格式的配置字符串
            strategy: 合并策略
        
        Returns:
            导入的配置字典
        """
        config_data = json.loads(json_content)
        return self.import_config_str(config_data, strategy)
    
    def import_config_str(
        self,
        config_data: Dict[str, Any],
        strategy: str = "merge"
    ) -> Dict[str, Any]:
        """
        从字典导入配置
        
        Args:
            config_data: 配置字典
            strategy: 合并策略
        
        Returns:
            导入的配置字典
        """
        if strategy == "replace":
            self._config = deepcopy(config_data)
        elif strategy == "merge":
            self._config = self._deep_merge(self._config, config_data)
        else:
            raise ValueError(f"未知的合并策略: {strategy}")
        
        return deepcopy(config_data)


# ── 便捷函数 ─────────────────────────────────────────────────────────

_config_instance: Optional[UnifiedConfig] = None


def get_config() -> UnifiedConfig:
    """获取配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = UnifiedConfig.get_instance()
    return _config_instance


def get(key: str, default: Any = None) -> Any:
    """快捷函数：获取配置值"""
    return get_config().get(key, default)


def set_config(key: str, value: Any) -> None:
    """快捷函数：设置配置值"""
    get_config().set(key, value)


def import_config(
    path: Optional[Path] = None,
    strategy: str = "merge",
    validate: bool = True
) -> Dict[str, Any]:
    """
    快捷函数：从文件导入配置
    
    Args:
        path: 导入文件路径
        strategy: 合并策略 (merge | replace | validate)
        validate: 是否验证配置结构
    
    Returns:
        导入的配置字典
    """
    return get_config().import_config(path, strategy, validate)


def export_config() -> Dict[str, Any]:
    """
    快捷函数：导出当前配置
    
    Returns:
        配置字典
    """
    return get_config().export()


def save_config(path: Optional[Path] = None) -> None:
    """
    快捷函数：保存配置到文件
    
    Args:
        path: 保存路径
    """
    get_config().save(path)


def load_config(path: Optional[Path] = None, strategy: str = "merge") -> Dict[str, Any]:
    """
    快捷函数：加载配置（别名）
    
    Args:
        path: 导入文件路径
        strategy: 合并策略
    
    Returns:
        导入的配置字典
    """
    return get_config().import_config(path, strategy)


# ── 预定义配置访问 ──────────────────────────────────────────────────

def get_ollama_endpoint(timeout: Optional[int] = None) -> Dict[str, Any]:
    """
    获取 Ollama 端点配置
    
    Returns:
        dict: {"url": str, "timeout": int, "max_retries": int}
    """
    config = get_config()
    result = {
        "url": config.get_ollama_url(),
        "timeout": timeout or config.get_ollama_timeout(),
        "max_retries": config.get("endpoints.ollama.max_retries", 3),
    }
    return result


def get_cloud_sync_config() -> Dict[str, Any]:
    """获取云同步配置"""
    config = get_config()
    return {
        "url": config.get("endpoints.cloud_sync.url", "ws://localhost:8765/sync"),
        "timeout": config.get("endpoints.cloud_sync.timeout", 30),
        "retry_delay": config.get("endpoints.cloud_sync.retry_delay", 5),
    }


def get_browser_automation_config() -> Dict[str, Any]:
    """获取浏览器自动化配置"""
    config = get_config()
    return {
        "timeout": config.get_timeout("browser"),
        "max_retries": config.get("retries.default", 3),
    }


def get_commission_config(module: Optional[str] = None) -> Dict[str, Any]:
    """
    获取佣金系统配置
    
    Args:
        module: 可选，指定模块名称
    
    Returns:
        佣金配置字典
    """
    return get_config().get_commission_config(module)


def get_decentralized_config() -> Dict[str, Any]:
    """获取去中心化知识系统配置"""
    return get_config().get_decentralized_config()


def get_provider_config(slot: Optional[str] = None) -> Dict[str, Any]:
    """
    获取模型Provider槽位配置
    
    Args:
        slot: 可选，指定槽位名称
    
    Returns:
        Provider配置字典
    """
    return get_config().get_provider_config(slot)


def get_email_config() -> Dict[str, Any]:
    """获取邮件通知配置"""
    return get_config().get_email_config()


def get_browser_gateway_config() -> Dict[str, Any]:
    """获取浏览器网关配置"""
    return get_config().get_browser_gateway_config()


def get_security_config(category: str = None) -> Dict[str, Any]:
    """
    获取安全/密钥管理配置
    
    Args:
        category: 可选，指定配置类别
    
    Returns:
        安全配置字典
    """
    return get_config().get_security_config(category)


def get_key_rotation_config() -> Dict[str, Any]:
    """获取密钥轮转配置"""
    return get_config().get_key_rotation_config()


def get_key_health_config() -> Dict[str, Any]:
    """获取密钥健康监控配置"""
    return get_config().get_key_health_config()


# ── Smart Config 便捷函数 ───────────────────────────────────────────

def detect_environment() -> RuntimeEnvironment:
    """检测运行时环境"""
    return get_config().detect_runtime_environment()


def get_recommended_profile() -> str:
    """根据环境获取推荐配置profile"""
    return get_config().get_recommended_profile()


def apply_profile(profile: str = None) -> Dict[str, Any]:
    """应用配置profile"""
    return get_config().apply_profile(profile)


def get_runtime_env() -> RuntimeEnvironment:
    """获取运行时环境"""
    return get_config().get_runtime_environment()


# ── 初始化入口 ──────────────────────────────────────────────────────

def init_config() -> UnifiedConfig:
    """初始化配置模块"""
    return UnifiedConfig.get_instance()
