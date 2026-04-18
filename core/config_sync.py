"""
配置同步管理器
Config Sync Manager

功能：
  · 用户配置"一次设置，到处同步"
  · 启动时自动从服务器拉取最新配置
  · 保存配置时自动推送到服务器
  · 离线时使用本地配置，恢复后自动同步
  · 支持按配置键（config_key）增量同步

架构：
  · 身份标识：user_token（用户生成，所有设备相同即共享配置）
  · 存储：本地 ~/.hermes-desktop/config_sync_token.json（仅存储 token）
  · 同步策略：last-write-wins（以服务器时间戳为准）
  · API：POST/GET/DELETE /api/config/sync（通过 relay_server）

配置键（config_key）：
  - app:        窗口状态、主题等
  - ollama:     Ollama 服务配置
  - model_market: 模型市场配置
  - search:    搜索配置
  - agent:     Agent 行为配置
  - writing:   写作配置
"""

import os
import json
import time
import logging
import platform
import uuid
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 路径工具 ──────────────────────────────────────────────────────────

def _get_config_dir() -> Path:
    """获取配置目录"""
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif platform.system() == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    cfg = base / "hermes-desktop"
    cfg.mkdir(parents=True, exist_ok=True)
    return cfg


# ── 数据模型 ──────────────────────────────────────────────────────────

@dataclass
class SyncStatus:
    """同步状态"""
    last_sync_at: int = 0          # 上次同步时间戳
    last_push_at: int = 0         # 上次推送时间戳
    last_pull_at: int = 0         # 上次拉取时间戳
    server_reachable: bool = False
    sync_error: str = ""
    pending_push: bool = False    # 是否有待推送的更改


@dataclass
class SyncResult:
    """同步结果"""
    success: bool
    pushed_keys: List[str] = field(default_factory=list)
    pulled_keys: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)  # 冲突的配置键
    error: str = ""
    server_timestamp: int = 0


# ── ConfigSyncManager ────────────────────────────────────────────────

class ConfigSyncManager:
    """
    配置同步管理器

    使用方式：
    1. 初始化：sync = ConfigSyncManager(relay_url)
    2. 登录/注册：sync.login(user_token) 或 sync.register()
    3. 启动同步：sync.start_auto_sync()
    4. 保存配置：sync.push_config("ollama", ollama_config)
    5. 拉取配置：sync.pull_all_configs()

    离线行为：
    - push_config() 失败时将配置暂存到待推送队列
    - 恢复连接后自动重试
    """

    # 配置键到 AppConfig 字段的映射
    CONFIG_KEY_MAP = {
        "app": "app",
        "ollama": "ollama",
        "model_market": "model_market",
        "search": "search",
        "agent": "agent",
        "writing": "writing",
    }

    def __init__(
        self,
        relay_url: str = "http://localhost:8766",
        auto_sync: bool = True,
        sync_interval: int = 300,  # 自动同步间隔（秒）
    ):
        self.relay_url = relay_url.rstrip("/")
        self.sync_interval = sync_interval
        self.auto_sync = auto_sync

        # 身份
        self._user_token: Optional[str] = None
        self._client_id: str = str(uuid.uuid4())[:8]  # 本设备 ID

        # 状态
        self.status = SyncStatus()
        self._lock = threading.RLock()

        # 待推送队列（离线时暂存）
        self._pending_queue: Dict[str, Dict[str, Any]] = {}

        # 定时器
        self._sync_timer: Optional[threading.Timer] = None
        self._running = False

        # HTTP 客户端（懒加载）
        self._http = None

        # 加载本地存储的 token
        self._load_local_token()

    # ── HTTP 客户端（延迟导入，避免不必要的依赖）────────────────────

    def _get_http(self):
        """获取 HTTP 客户端"""
        if self._http is None:
            import httpx
            self._http = httpx.Client(timeout=10.0)
        return self._http

    # ── Token 管理 ──────────────────────────────────────────────────

    def _get_token_file(self) -> Path:
        return _get_config_dir() / "config_sync_token.json"

    def _load_local_token(self):
        """从本地文件加载 user_token"""
        path = self._get_token_file()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._user_token = data.get("user_token")
                self._client_id = data.get("client_id", self._client_id)
                if self._user_token:
                    logger.info(f"已加载本地 user_token: {self._user_token[:8]}...")
            except Exception as e:
                logger.warning(f"加载 token 失败: {e}")

    def _save_local_token(self):
        """保存 user_token 到本地文件"""
        path = self._get_token_file()
        data = {
            "user_token": self._user_token,
            "client_id": self._client_id,
            "saved_at": int(time.time()),
        }
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"保存 token 失败: {e}")

    # ── 身份管理 ────────────────────────────────────────────────────

    @property
    def is_logged_in(self) -> bool:
        """是否已登录（已有 user_token）"""
        return bool(self._user_token)

    def login(self, user_token: str) -> bool:
        """
        使用已有的 user_token 登录

        Args:
            user_token: 用户令牌（所有设备使用相同 token 则共享配置）

        Returns:
            bool: 是否登录成功
        """
        if len(user_token) < 8:
            logger.error("user_token 长度至少为 8")
            return False

        with self._lock:
            self._user_token = user_token
            self._save_local_token()
            logger.info(f"已设置 user_token: {user_token[:8]}...")
            return True

    def register(self) -> str:
        """
        注册新身份（生成新的 user_token）

        Returns:
            str: 新生成的 user_token
        """
        import secrets
        token = secrets.token_hex(24)  # 48 字符的随机 token
        self.login(token)
        logger.info(f"已注册新身份: {token[:8]}...")
        return token

    def logout(self):
        """退出登录（清除本地 token，但不删除服务器数据）"""
        with self._lock:
            self._user_token = None
            self._save_local_token()
            self.stop_auto_sync()
            logger.info("已退出登录")

    def get_user_token(self) -> Optional[str]:
        """获取当前 user_token（用于显示给用户）"""
        return self._user_token

    # ── 服务器可达性检测 ─────────────────────────────────────────────

    def _check_server(self) -> bool:
        """检测服务器是否可达"""
        try:
            client = self._get_http()
            resp = client.get(f"{self.relay_url}/api/health", timeout=5.0)
            self.status.server_reachable = (resp.status_code == 200)
            return self.status.server_reachable
        except Exception as e:
            self.status.server_reachable = False
            logger.debug(f"服务器不可达: {e}")
            return False

    # ── 推送配置 ────────────────────────────────────────────────────

    def push_config(
        self,
        config_key: str,
        config_data: Dict[str, Any],
        platform_name: str = "",
    ) -> bool:
        """
        推送单个配置块到服务器

        Args:
            config_key: 配置键（如 'ollama', 'search'）
            config_data: 配置数据字典
            platform_name: 平台名称（可选）

        Returns:
            bool: 是否推送成功
        """
        if not self._user_token:
            logger.warning("未登录，无法推送配置")
            # 离线：加入待推送队列
            self._pending_queue[config_key] = config_data
            self.status.pending_push = True
            return False

        platform_name = platform_name or platform.system().lower()

        try:
            client = self._get_http()
            resp = client.post(
                f"{self.relay_url}/api/config/sync",
                json={
                    "user_token": self._user_token,
                    "config_key": config_key,
                    "config_data": config_data,
                    "client_id": self._client_id,
                    "platform": platform_name,
                    "version": "2.0.0",
                },
                timeout=10.0,
            )

            if resp.status_code == 200:
                result = resp.json()
                self.status.last_push_at = result.get("server_timestamp", int(time.time()))
                self.status.sync_error = ""

                # 成功推送后，清除待推送队列中对应的项
                if config_key in self._pending_queue:
                    del self._pending_queue[config_key]
                if not self._pending_queue:
                    self.status.pending_push = False

                logger.info(f"配置推送成功: {config_key}")
                return True
            else:
                logger.warning(f"配置推送失败: HTTP {resp.status_code}")
                self._add_to_pending(config_key, config_data)
                return False

        except Exception as e:
            logger.warning(f"配置推送异常: {e}")
            self.status.sync_error = str(e)
            self._add_to_pending(config_key, config_data)
            return False

    def _add_to_pending(self, config_key: str, config_data: Dict[str, Any]):
        """加入待推送队列"""
        with self._lock:
            self._pending_queue[config_key] = config_data
            self.status.pending_push = True

    def push_all_configs(self, configs: Dict[str, Dict[str, Any]]) -> SyncResult:
        """
        批量推送多个配置块

        Args:
            configs: {config_key: config_data, ...}

        Returns:
            SyncResult: 同步结果
        """
        result = SyncResult(success=True)
        platform_name = platform.system().lower()

        for key, data in configs.items():
            ok = self.push_config(key, data, platform_name)
            if ok:
                result.pushed_keys.append(key)
            else:
                result.success = False

        return result

    # ── 拉取配置 ────────────────────────────────────────────────────

    def pull_config(self, config_key: str) -> Optional[Dict[str, Any]]:
        """
        从服务器拉取单个配置块

        Args:
            config_key: 配置键

        Returns:
            配置数据字典，失败返回 None
        """
        if not self._user_token:
            logger.warning("未登录，无法拉取配置")
            return None

        try:
            client = self._get_http()
            resp = client.get(
                f"{self.relay_url}/api/config/sync",
                params={
                    "user_token": self._user_token,
                    "config_key": config_key,
                },
                timeout=10.0,
            )

            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    self.status.last_pull_at = result.get("server_timestamp", int(time.time()))
                    logger.info(f"配置拉取成功: {config_key}")
                    return result.get("config_data", {})
                else:
                    logger.warning(f"配置拉取返回失败: {result.get('error')}")
                    return None
            else:
                logger.warning(f"配置拉取失败: HTTP {resp.status_code}")
                return None

        except Exception as e:
            logger.warning(f"配置拉取异常: {e}")
            self.status.sync_error = str(e)
            return None

    def pull_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        从服务器拉取所有配置

        Returns:
            {config_key: config_data, ...}
        """
        if not self._user_token:
            logger.warning("未登录，无法拉取配置")
            return {}

        try:
            client = self._get_http()
            resp = client.get(
                f"{self.relay_url}/api/config/sync",
                params={"user_token": self._user_token},
                timeout=10.0,
            )

            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    self.status.last_pull_at = result.get("server_timestamp", int(time.time()))
                    self.status.server_reachable = True
                    self.status.sync_error = ""
                    configs = result.get("configs", {})
                    logger.info(f"配置拉取成功，共 {len(configs)} 个配置块")
                    return configs
                else:
                    logger.warning(f"配置拉取返回失败: {result.get('error')}")
                    return {}
            else:
                logger.warning(f"配置拉取失败: HTTP {resp.status_code}")
                return {}

        except Exception as e:
            logger.warning(f"配置拉取异常: {e}")
            self.status.sync_error = str(e)
            return {}

    # ── 查询 ────────────────────────────────────────────────────────

    def list_remote_keys(self) -> List[Dict[str, Any]]:
        """
        查询服务器上已存储的配置键列表

        Returns:
            [{key, updated_at, platform, client_id}, ...]
        """
        if not self._user_token:
            return []

        try:
            client = self._get_http()
            resp = client.get(
                f"{self.relay_url}/api/config/keys",
                params={"user_token": self._user_token},
                timeout=10.0,
            )
            if resp.status_code == 200:
                result = resp.json()
                return result.get("keys", [])
            return []
        except Exception as e:
            logger.warning(f"查询配置键失败: {e}")
            return []

    # ── 清除 ────────────────────────────────────────────────────────

    def clear_remote_config(self, config_key: Optional[str] = None) -> bool:
        """
        清除服务器上的配置

        Args:
            config_key: None 表示清除所有，否则只清除该配置块

        Returns:
            bool: 是否成功
        """
        if not self._user_token:
            return False

        try:
            client = self._get_http()
            params = {"user_token": self._user_token}
            if config_key:
                params["config_key"] = config_key

            resp = client.request(
                "DELETE",
                f"{self.relay_url}/api/config/sync",
                params=params,
                timeout=10.0,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"清除配置失败: {e}")
            return False

    # ── 自动同步 ────────────────────────────────────────────────────

    def start_auto_sync(self, interval: Optional[int] = None):
        """
        启动自动同步（定时拉取 + 推送待发送队列）

        Args:
            interval: 同步间隔（秒），默认使用初始化时的值
        """
        if self._running:
            return

        self._running = True
        interval = interval or self.sync_interval

        def _sync_loop():
            if not self._running:
                return
            try:
                self._do_auto_sync()
            except Exception as e:
                logger.warning(f"自动同步异常: {e}")
            finally:
                if self._running:
                    self._sync_timer = threading.Timer(interval, _sync_loop)
                    self._sync_timer.daemon = True
                    self._sync_timer.start()

        logger.info(f"启动自动同步，间隔 {interval} 秒")
        self._sync_timer = threading.Timer(interval, _sync_loop)
        self._sync_timer.daemon = True
        self._sync_timer.start()

    def stop_auto_sync(self):
        """停止自动同步"""
        self._running = False
        if self._sync_timer:
            self._sync_timer.cancel()
            self._sync_timer = None
        logger.info("已停止自动同步")

    def _do_auto_sync(self):
        """执行一次自动同步"""
        if not self._user_token:
            return

        # 先推送待发送队列
        if self._pending_queue:
            pending = dict(self._pending_queue)
            for key, data in pending.items():
                self.push_config(key, data)

        # 再拉取最新配置（不覆盖本地有未推送更改的配置）
        remote = self.pull_all_configs()
        # 注：合并逻辑由调用方在 AppConfig 层面处理

    # ── 完整同步（推送本地 + 拉取远端，智能合并）────────────────────

    def full_sync(
        self,
        local_configs: Dict[str, Dict[str, Any]],
        on_merge: Callable[[str, Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
    ) -> SyncResult:
        """
        完整双向同步（本地 push + 远端 pull + 智能合并）

        Args:
            local_configs: 本地配置 {config_key: config_data}
            on_merge: 合并回调 (config_key, local_data, remote_data) -> merged_data
                     如果返回 None 表示不使用远程数据

        Returns:
            SyncResult: 包含需要合并的冲突项
        """
        result = SyncResult(success=True)

        if not self._user_token:
            result.success = False
            result.error = "Not logged in"
            return result

        if not self._check_server():
            result.success = False
            result.error = "Server unreachable"
            return result

        # Step 1: 推送所有本地配置
        push_result = self.push_all_configs(local_configs)
        result.pushed_keys = push_result.pushed_keys

        # Step 2: 拉取远端配置
        remote_configs = self.pull_all_configs()

        # Step 3: 检测冲突（双方都有，且数据不同）
        for key, remote_data in remote_configs.items():
            if key in local_configs:
                local_data = local_configs[key]
                if local_data != remote_data:
                    # 冲突：使用 on_merge 回调合并
                    merged = on_merge(key, local_data, remote_data)
                    if merged is not None:
                        result.conflicts.append(key)
                        # 合并后推送
                        self.push_config(key, merged)
                        result.pushed_keys.append(key)

        result.pulled_keys = list(remote_configs.keys())
        result.success = True
        result.server_timestamp = int(time.time())
        return result

    # ── AppConfig 级别的同步 ─────────────────────────────────────────

    def sync_app_config(
        self,
        local_config: "AppConfig",  # noqa: F821
        save_callback: Callable[["AppConfig"], None],  # noqa: F821
    ) -> bool:
        """
        AppConfig 级别的便捷同步方法

        Args:
            local_config: 当前本地 AppConfig 对象
            save_callback: 保存配置到本地的回调函数

        Returns:
            bool: 是否有新的远程配置被合并
        """
        # 将 AppConfig 转换为 dict
        local_configs = {}
        for key in self.CONFIG_KEY_MAP:
            section = getattr(local_config, key, None)
            if section is not None:
                if hasattr(section, "model_dump"):
                    local_configs[key] = section.model_dump()
                else:
                    local_configs[key] = dict(section) if section else {}

        # 拉取远端
        remote_configs = self.pull_all_configs()
        if not remote_configs:
            return False

        # 简单合并策略：远程覆盖本地
        # （如需更复杂策略，使用 full_sync + on_merge）
        merged = False
        for key, remote_data in remote_configs.items():
            if key in local_configs and remote_data != local_configs[key]:
                logger.info(f"合并远程配置: {key}")
                # 应用到 local_config
                section = getattr(local_config, key, None)
                if section is not None and hasattr(section, "model_validate"):
                    try:
                        updated = section.model_validate(remote_data)
                        setattr(local_config, key, updated)
                        merged = True
                    except Exception as e:
                        logger.warning(f"合并配置 {key} 失败: {e}")

        if merged:
            save_callback(local_config)
            logger.info("已合并远程配置并保存")

        return merged

    # ── 状态信息 ────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return {
            "logged_in": self.is_logged_in,
            "user_token": (self._user_token[:8] + "...") if self._user_token else None,
            "client_id": self._client_id,
            "last_sync_at": self.status.last_sync_at,
            "last_push_at": self.status.last_push_at,
            "last_pull_at": self.status.last_pull_at,
            "server_reachable": self.status.server_reachable,
            "pending_push_keys": list(self._pending_queue.keys()),
            "pending_push_count": len(self._pending_queue),
            "auto_sync_running": self._running,
        }

    def __repr__(self):
        return (f"ConfigSyncManager(token={self._user_token[:8] if self._user_token else None}..., "
                f"reachable={self.status.server_reachable}, "
                f"pending={len(self._pending_queue)})")


# ── 单例访问 ──────────────────────────────────────────────────────────

_sync_manager: Optional[ConfigSyncManager] = None
_sync_lock = threading.Lock()


def get_sync_manager(
    relay_url: str = "http://localhost:8766",
    auto_sync: bool = False,
) -> ConfigSyncManager:
    """
    获取 ConfigSyncManager 单例

    Args:
        relay_url: Relay 服务器地址
        auto_sync: 是否启用自动同步（仅首次生效）
    """
    global _sync_manager
    with _sync_lock:
        if _sync_manager is None:
            _sync_manager = ConfigSyncManager(relay_url=relay_url, auto_sync=auto_sync)
        return _sync_manager


# ── 快捷函数 ──────────────────────────────────────────────────────────

def quick_sync(
    user_token: str,
    local_config_dict: Dict[str, Any],
    relay_url: str = "http://localhost:8766",
) -> Optional[Dict[str, Any]]:
    """
    一次性拉取远程配置（快捷函数）

    用于启动时快速同步：
        remote = quick_sync(token, local_config_dict)
        if remote:
            # 有远程配置，合并使用

    Returns:
        远端配置字典，失败返回 None
    """
    manager = ConfigSyncManager(relay_url=relay_url)
    if not manager.login(user_token):
        return None
    return manager.pull_all_configs()
