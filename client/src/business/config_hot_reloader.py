"""
Config Hot Reloader - 配置热更新

监听配置文件变化，自动重载并通知相关组件。
支持优雅重启、版本回滚、变更历史。

设计理念：
1. 文件监听：watchdog / QFileSystemWatcher
2. 自动重载：检测变化后自动重新加载
3. 事件通知：通过 EventBus 发布配置变更事件
4. 优雅重启：不中断正在处理的请求
5. 版本回滚：保存变更历史，支持回滚
"""

import os
import time
import traceback
import json
import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class ReloadStrategy(Enum):
    """重载策略"""
    IMMEDIATE = "immediate"   # 立即重载
    DEBOUNCED = "debounced" # 防抖（等待文件稳定）
    SCHEDULED = "scheduled" # 定时重载


class ConfigChangeType(Enum):
    """配置变更类型"""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class ConfigChange:
    """配置变更记录"""
    config_path: str
    change_type: ConfigChangeType
    old_value: Any = None
    new_value: Any = None
    timestamp: float = field(default_factory=time.time)
    reloaded: bool = False


class ConfigHotReloader:
    """
    配置热重载器

    监听配置文件变化，自动重载并通知相关组件。

    使用示例：
        reloader = ConfigHotReloader()
        reloader.add_watch_path("config/config_data.json")
        reloader.add_reload_callback(lambda changes: print(f"Config reloaded: {changes}"))
        reloader.start()

        # 手动触发重载
        reloader.reload_all()

        # 回滚到上一个版本
        reloader.rollback()
    """

    def __init__(
        self,
        debounce_delay: float = 0.5,  # 防抖延迟（秒）
        max_history: int = 50,       # 最大历史记录数
        strategy: ReloadStrategy = ReloadStrategy.DEBOUNCED,
    ):
        """
        初始化热重载器

        Args:
            debounce_delay: 防抖延迟（秒）
            max_history: 最大历史记录数
            strategy: 重载策略
        """
        self._debounce_delay = debounce_delay
        self._max_history = max_history
        self._strategy = strategy

        self._watch_paths: List[str] = []
        self._callbacks: List[Callable[[List[ConfigChange]], None]] = []
        self._history: List[Dict[str, Any]] = []  # 配置快照历史
        self._lock = threading.RLock()

        # watchdog 观察者
        self._observer = None
        self._monitoring = False

        # 防抖定时器
        self._debounce_timer: Optional[threading.Timer] = None

        # 缓存的配置数据
        self._config_cache: Dict[str, Any] = {}
        self._config_mtime: Dict[str, float] = {}  # 文件修改时间

        logger.info(
            f"[ConfigHotReloader] Initialized: "
            f"strategy={strategy.value}, debounce_delay={debounce_delay}s"
        )

    def add_watch_path(self, path: str) -> None:
        """
        添加监听路径

        Args:
            path: 文件路径或目录路径
        """
        with self._lock:
            abs_path = os.path.abspath(path)
            if abs_path not in self._watch_paths:
                self._watch_paths.append(abs_path)
                logger.info(f"[ConfigHotReloader] Added watch path: {abs_path}")

    def remove_watch_path(self, path: str) -> None:
        """
        移除监听路径

        Args:
            path: 文件路径或目录路径
        """
        with self._lock:
            abs_path = os.path.abspath(path)
            if abs_path in self._watch_paths:
                self._watch_paths.remove(abs_path)
                logger.info(f"[ConfigHotReloader] Removed watch path: {abs_path}")

    def add_reload_callback(self, callback: Callable[[List[ConfigChange]], None]) -> None:
        """
        添加重载回调

        Args:
            callback: 回调函数，接收 ConfigChange 列表
        """
        with self._lock:
            self._callbacks.append(callback)
            logger.debug(f"[ConfigHotReloader] Added reload callback ({len(self._callbacks)} total)")

    def remove_reload_callback(self, callback: Callable[[List[ConfigChange]], None]) -> None:
        """移除重载回调"""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def start(self) -> None:
        """启动文件监听"""
        if self._monitoring:
            logger.warning("[ConfigHotReloader] Already monitoring")
            return

        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class ConfigFileHandler(FileSystemEventHandler):
                def __init__(self, reloader):
                    self._reloader = reloader

                def on_any_event(self, event):
                    self._reloader._on_file_changed(event)

            self._observer = Observer()
            handler = ConfigFileHandler(self)

            for path in self._watch_paths:
                watch_dir = path if os.path.isdir(path) else os.path.dirname(path)
                if os.path.exists(watch_dir):
                    self._observer.schedule(handler, watch_dir, recursive=False)
                    logger.info(f"[ConfigHotReloader] Watching directory: {watch_dir}")

            self._observer.start()
            self._monitoring = True
            logger.info("[ConfigHotReloader] Started monitoring")

        except ImportError:
            logger.warning("[ConfigHotReloader] watchdog not installed, using polling mode")
            self._start_polling()

        except Exception as e:
            logger.error(f"[ConfigHotReloader] Failed to start monitoring: {e}")
            logger.error(traceback.format_exc())

    def _start_polling(self) -> None:
        """启动轮询模式（watchdog 不可用时的回退方案）"""
        self._monitoring = True
        self._polling_thread = threading.Thread(target=self._poll_files, daemon=True)
        self._polling_thread.start()
        logger.info("[ConfigHotReloader] Started polling mode")

    def _poll_files(self) -> None:
        """轮询文件变化"""
        while self._monitoring:
            try:
                self._check_file_changes()
                time.sleep(2)  # 每 2 秒检查一次
            except Exception as e:
                logger.error(f"[ConfigHotReloader] Polling error: {e}")
                time.sleep(5)

    def _check_file_changes(self) -> None:
        """检查文件变化（轮询模式）"""
        changes = []

        with self._lock:
            for path in self._watch_paths:
                if not os.path.isfile(path):
                    continue

                mtime = os.path.getmtime(path)
                if path not in self._config_mtime:
                    # 第一次见这个文件
                    self._config_mtime[path] = mtime
                    continue

                if mtime != self._config_mtime[path]:
                    # 文件已修改
                    old_value = self._config_cache.get(path)
                    new_value = self._load_config_file(path)

                    change = ConfigChange(
                        config_path=path,
                        change_type=ConfigChangeType.MODIFIED,
                        old_value=old_value,
                        new_value=new_value,
                    )
                    changes.append(change)

                    # 更新缓存
                    self._config_cache[path] = new_value
                    self._config_mtime[path] = mtime

        if changes:
            self._on_config_changed(changes)

    def _on_file_changed(self, event) -> None:
        """
        文件变化回调（watchdog）

        Args:
            event: watchdog 事件对象
        """
        if self._strategy == ReloadStrategy.DEBOUNCED:
            # 防抖：延迟执行
            if self._debounce_timer:
                self._debounce_timer.cancel()

            self._debounce_timer = threading.Timer(
                self._debounce_delay,
                self._reload_debounced, [event]
            )
            self._debounce_timer.start()
        else:
            # 立即重载
            self._reload_immediate(event)

    def _reload_debounced(self, event) -> None:
        """防抖后执行重载"""
        changes = self._detect_changes(event.src_path)
        if changes:
            self._on_config_changed(changes)

    def _reload_immediate(self, event) -> None:
        """立即重载"""
        changes = self._detect_changes(event.src_path)
        if changes:
            self._on_config_changed(changes)

    def _detect_changes(self, file_path: str) -> List[ConfigChange]:
        """
        检测配置文件变化

        Args:
            file_path: 文件路径

        Returns:
            ConfigChange 列表
        """
        changes = []

        with self._lock:
            if not os.path.isfile(file_path):
                return changes

            old_value = self._config_cache.get(file_path)
            new_value = self._load_config_file(file_path)

            if old_value != new_value:
                change_type = ConfigChangeType.MODIFIED
                if old_value is None:
                    change_type = ConfigChangeType.CREATED
                elif new_value is None:
                    change_type = ConfigChangeType.DELETED

                change = ConfigChange(
                    config_path=file_path,
                    change_type=change_type,
                    old_value=old_value,
                    new_value=new_value,
                )
                changes.append(change)

                # 更新缓存
                if new_value is not None:
                    self._config_cache[file_path] = new_value
                else:
                    self._config_cache.pop(file_path, None)

        return changes

    def _on_config_changed(self, changes: List[ConfigChange]) -> None:
        """
        配置变更处理

        Args:
            changes: ConfigChange 列表
        """
        logger.info(f"[ConfigHotReloader] Config changed: {len(changes)} file(s)")

        # 保存历史
        self._save_history(changes)

        # 增量更新 config_provider 的缓存（只更新变更的项）
        self._update_config_provider_cache_incremental(changes)

        # 通知回调
        with self._lock:
            for callback in self._callbacks:
                try:
                    callback(changes)
                except Exception as e:
                    logger.error(f"[ConfigHotReloader] Callback error: {e}")
                    logger.error(traceback.format_exc())

        # 发布 EventBus 事件
        self._publish_config_changed_event(changes)

    def _clear_config_provider_cache(self) -> None:
        """清除 config_provider 的缓存（兼容旧代码）"""
        try:
            from core import config_provider
            if hasattr(config_provider, '_cached_config'):
                config_provider._cached_config = None
                logger.info("[ConfigHotReloader] Cleared config_provider cache")
        except Exception as e:
            logger.error(f"[ConfigHotReloader] Failed to clear config_provider cache: {e}")

    def _update_config_provider_cache_incremental(self, changes: List[ConfigChange]) -> None:
        """
        增量更新 config_provider 的缓存

        只更新变更的配置项，避免全量清除缓存后重新加载的开销。

        Args:
            changes: ConfigChange 列表
        """
        try:
            from core import config_provider

            # 确保缓存已初始化
            if config_provider._cached_config is None:
                config_provider._load_config()
                return  # _load_config() 已经填充了缓存

            # 增量更新：遍历变更，只更新变更的配置项
            for change in changes:
                if change.change_type == ConfigChangeType.DELETED:
                    # 文件被删除：清除整个缓存，下次重新加载
                    config_provider._cached_config = None
                    logger.warning(
                        f"[ConfigHotReloader] Config file deleted: {change.config_path}, "
                        f"clearing entire cache"
                    )
                    return

                new_value = change.new_value
                if not isinstance(new_value, dict):
                    continue

                # 更新 ollama_url（如果配置中包含）
                if "ollama_url" in new_value:
                    old_url = config_provider._cached_config.get("ollama_url")
                    new_url = new_value["ollama_url"]
                    if old_url != new_url:
                        config_provider._cached_config["ollama_url"] = new_url
                        logger.info(
                            f"[ConfigHotReloader] Incremental update: "
                            f"ollama_url = {new_url}"
                        )

                # 更新 models（如果配置中包含）
                if "models" in new_value and isinstance(new_value["models"], dict):
                    if "models" not in config_provider._cached_config:
                        config_provider._cached_config["models"] = {}
                    config_provider._cached_config["models"].update(new_value["models"])
                    logger.info(
                        f"[ConfigHotReloader] Incremental update: "
                        f"models = {list(new_value['models'].keys())}"
                    )

            logger.info("[ConfigHotReloader] Incremental cache update completed")

        except Exception as e:
            logger.error(f"[ConfigHotReloader] Incremental update failed: {e}")
            logger.error(traceback.format_exc())
            # 失败时回退到全量清除
            try:
                config_provider._cached_config = None
                logger.warning("[ConfigHotReloader] Fallback: cleared entire cache")
            except Exception:
                pass

    def _publish_config_changed_event(self, changes: List[ConfigChange]) -> None:
        """发布配置变更事件到 EventBus"""
        try:
            from core.plugin_framework.event_bus import Event, get_event_bus
            event_bus = get_event_bus()

            event = Event(
                type="config.changed",
                data={
                    "changes": [
                        {
                            "path": c.config_path,
                            "type": c.change_type.value,
                            "timestamp": c.timestamp,
                        }
                        for c in changes
                    ],
                    "timestamp": time.time(),
                },
                source="ConfigHotReloader",
            )
            event_bus.publish(event)
            logger.debug("[ConfigHotReloader] Published config.changed event")

        except Exception as e:
            logger.error(f"[ConfigHotReloader] Failed to publish event: {e}")

    def _save_history(self, changes: List[ConfigChange]) -> None:
        """保存配置快照历史"""
        with self._lock:
            snapshot = {
                "timestamp": time.time(),
                "changes": [c.__dict__ for c in changes],
                "config_cache": self._config_cache.copy(),
            }
            self._history.append(snapshot)

            # 限制历史记录数
            if len(self._history) > self._max_history:
                self._history.pop(0)

    def reload_all(self) -> List[ConfigChange]:
        """
        手动触发重载所有配置

        Returns:
            ConfigChange 列表
        """
        changes = []
        with self._lock:
            for path in self._watch_paths:
                file_changes = self._detect_changes(path)
                changes.extend(file_changes)

        if changes:
            self._on_config_changed(changes)

        return changes

    def get_current_config(self, path: Optional[str] = None) -> Any:
        """
        获取当前配置

        Args:
            path: 配置文件路径（None = 返回所有）

        Returns:
            配置数据
        """
        with self._lock:
            if path:
                return self._config_cache.get(path)
            return self._config_cache.copy()

    def rollback(self, steps: int = 1) -> bool:
        """
        回滚到上一个版本

        Args:
            steps: 回滚步数

        Returns:
            是否成功回滚
        """
        with self._lock:
            if len(self._history) < steps:
                logger.warning(f"[ConfigHotReloader] Not enough history to rollback {steps} steps")
                return False

            # 获取目标历史
            target = self._history[-steps]
            self._config_cache = target["config_cache"].copy()

            # 写回配置文件
            for path, value in self._config_cache.items():
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(value, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.error(f"[ConfigHotReloader] Failed to rollback {path}: {e}")

            logger.info(f"[ConfigHotReloader] Rolled back {steps} step(s)")
            return True

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取变更历史

        Args:
            limit: 返回数量限制

        Returns:
            历史记录列表
        """
        with self._lock:
            return self._history[-limit:]

    def stop(self) -> None:
        """停止监听"""
        if not self._monitoring:
            return

        self._monitoring = False

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        if self._debounce_timer:
            self._debounce_timer.cancel()
            self._debounce_timer = None

        logger.info("[ConfigHotReloader] Stopped monitoring")

    def _load_config_file(self, path: str) -> Optional[Any]:
        """
        加载配置文件

        Args:
            path: 文件路径

        Returns:
            配置数据，失败则返回 None
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[ConfigHotReloader] Failed to load {path}: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "monitoring": self._monitoring,
                "watch_paths": len(self._watch_paths),
                "callbacks": len(self._callbacks),
                "history_size": len(self._history),
                "cached_configs": len(self._config_cache),
                "strategy": self._strategy.value,
                "debounce_delay": self._debounce_delay,
            }


# ──────────────────────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────────────────────

_reloader_instance: Optional[ConfigHotReloader] = None
_reloader_lock = threading.RLock()


def get_config_hot_reloader(
    debounce_delay: float = 0.5,
    max_history: int = 50,
) -> ConfigHotReloader:
    """
    获取配置热重载器单例

    Args:
        debounce_delay: 防抖延迟（秒）
        max_history: 最大历史记录数

    Returns:
        配置热重载器实例
    """
    global _reloader_instance
    with _reloader_lock:
        if _reloader_instance is None:
            _reloader_instance = ConfigHotReloader(
                debounce_delay=debounce_delay,
                max_history=max_history,
            )
        return _reloader_instance


def start_config_hot_reload(watch_paths: Optional[List[str]] = None) -> ConfigHotReloader:
    """
    启动配置热重载

    Args:
        watch_paths: 监听路径列表（None = 自动检测）

    Returns:
        配置热重载器实例
    """
    reloader = get_config_hot_reloader()

    if watch_paths:
        for path in watch_paths:
            reloader.add_watch_path(path)
    else:
        # 自动检测配置文件
        default_paths = [
            "config/config_data.json",
            "core/config/unified_config.py",
        ]
        for path in default_paths:
            if os.path.exists(path):
                reloader.add_watch_path(path)

    reloader.start()
    return reloader


def stop_config_hot_reload() -> None:
    """停止配置热重载"""
    global _reloader_instance
    with _reloader_lock:
        if _reloader_instance:
            _reloader_instance.stop()
            _reloader_instance = None
