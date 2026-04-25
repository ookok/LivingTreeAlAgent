# -*- coding: utf-8 -*-
"""
config_manager.py — 配置热更新

管理 Provider 系统的运行时配置，支持：
  - 运行时模型切换
  - 动态驱动策略
  - A/B 测试配置
  - 配置持久化与重载
  - 监听配置文件变化
  - 从 UnifiedConfig 读取配置
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .base import DriverMode, DriverState

if TYPE_CHECKING:
    from core.config.unified_config import UnifiedConfig

logger = logging.getLogger(__name__)


# ── 配置数据模型 ──────────────────────────────────────────────────

@dataclass
class ModelSlotConfig:
    """
    模型槽配置

    每个槽位代表一个可切换的模型配置。
    """
    slot_id: str = ""                          # 槽位 ID
    model_id: str = ""                         # 模型标识
    mode: str = "local_service"               # 驱动模式
    driver_name: str = ""                      # 驱动名称
    params: Dict[str, Any] = field(default_factory=dict)  # 驱动参数
    priority: int = 100                        # 路由优先级
    enabled: bool = True                       # 是否启用
    max_concurrent: int = 1                    # 最大并发
    timeout: float = 120.0                     # 超时时间


@dataclass
class ABTestConfig:
    """A/B 测试配置"""
    experiment_id: str = ""
    model: str = ""                            # 目标模型
    variants: Dict[str, float] = field(default_factory=dict)  # {driver_name: weight}
    enabled: bool = True
    start_time: Optional[float] = None
    end_time: Optional[float] = None


@dataclass
class ProviderConfig:
    """
    Provider 完整配置
    """
    # 默认模式
    default_mode: str = "local_service"

    # 模型槽位
    slots: List[ModelSlotConfig] = field(default_factory=list)

    # A/B 测试
    ab_tests: List[ABTestConfig] = field(default_factory=list)

    # 全局参数
    global_params: Dict[str, Any] = field(default_factory=dict)

    # 硬加载默认参数
    hard_load_defaults: Dict[str, Any] = field(default_factory=dict)

    # 本地服务默认参数
    local_service_defaults: Dict[str, Any] = field(default_factory=dict)

    # 云服务默认参数
    cloud_defaults: Dict[str, Any] = field(default_factory=dict)

    def get_slot(self, slot_id: str) -> Optional[ModelSlotConfig]:
        for slot in self.slots:
            if slot.slot_id == slot_id:
                return slot
        return None

    def get_enabled_slots(self) -> List[ModelSlotConfig]:
        return [s for s in self.slots if s.enabled]


# ── 配置管理器 ──────────────────────────────────────────────────

class UnifiedConfigMixin:
    """
    统一配置混入类
    
    从 UnifiedConfig 读取配置
    """
    
    _unified_config: Optional["UnifiedConfig"] = None
    
    def _get_unified_config(self) -> "UnifiedConfig":
        """获取统一配置实例"""
        if self._unified_config is None:
            from core.config.unified_config import UnifiedConfig
            self._unified_config = UnifiedConfig.get_instance()
        return self._unified_config
    
    def _load_from_unified_config(self) -> None:
        """从统一配置加载Provider配置"""
        try:
            unified = self._get_unified_config()
            
            # 加载槽位配置
            slots_config = unified.get("provider.slots", {})
            for slot_key, slot_data in slots_config.items():
                if slot_data:
                    slot = ModelSlotConfig(
                        slot_id=slot_key,
                        model_id=slot_data.get("model", ""),
                        driver_name=slot_data.get("provider", ""),
                        priority=slot_data.get("priority", 100),
                        enabled=slot_data.get("enabled", True),
                    )
                    # 检查是否已存在
                    existing = self._config.get_slot(slot_key)
                    if not existing:
                        self._config.slots.append(slot)
            
            # 加载策略配置
            strategy = unified.get("provider.strategy", {})
            if strategy:
                self._config.global_params.update({
                    "strategy_mode": strategy.get("mode", "failover"),
                    "health_check_interval": strategy.get("health_check_interval", 60),
                    "auto_switch": strategy.get("auto_switch", True),
                })
            
            logger.info("[ConfigManager] 已从 UnifiedConfig 加载配置")
            
        except Exception as e:
            logger.warning(f"[ConfigManager] 从统一配置加载失败: {e}")


class ProviderConfigManager(UnifiedConfigMixin):
    """
    Provider 配置管理器

    支持：
      - 从文件加载/保存配置
      - 运行时修改配置
      - 配置变更通知
      - 热重载
      - 从 UnifiedConfig 读取配置
    """

    DEFAULT_CONFIG_FILE = "provider_config.json"

    def __init__(
        self,
        config_path: str = "",
        on_change: Optional[Callable] = None,
        use_unified_config: bool = True,
    ):
        self._config = ProviderConfig()
        self._config_path = Path(config_path) if config_path else None
        self._on_change = on_change
        self._lock = threading.Lock()
        self._last_loaded: float = 0.0
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._use_unified_config = use_unified_config
        
        # 尝试从统一配置加载
        if use_unified_config:
            self._load_from_unified_config()

    @property
    def config(self) -> ProviderConfig:
        return self._config

    @property
    def config_path(self) -> Optional[Path]:
        return self._config_path

    # ── 加载与保存 ───────────────────────────────────────────

    def load_from_file(self, path: str = "") -> bool:
        """从 JSON 文件加载配置"""
        path = path or (str(self._config_path) if self._config_path else "")
        if not path:
            logger.warning("[ConfigManager] no config path specified")
            return False

        config_path = Path(path)
        if not config_path.exists():
            logger.warning(f"[ConfigManager] config file not found: {config_path}")
            return False

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                self._config = self._parse_config(data)
                self._config_path = config_path
                self._last_loaded = time.time()
            logger.info(f"[ConfigManager] loaded from {config_path}")
            self._notify_change("file_load")
            return True
        except Exception as e:
            logger.error(f"[ConfigManager] load failed: {e}")
            return False

    def save_to_file(self, path: str = "") -> bool:
        """保存配置到 JSON 文件"""
        path = path or (str(self._config_path) if self._config_path else "")
        if not path:
            logger.warning("[ConfigManager] no save path")
            return False
        try:
            with self._lock:
                data = self._serialize_config(self._config)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[ConfigManager] saved to {path}")
            return True
        except Exception as e:
            logger.error(f"[ConfigManager] save failed: {e}")
            return False

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典加载配置"""
        with self._lock:
            self._config = self._parse_config(data)
            self._last_loaded = time.time()
        logger.info("[ConfigManager] loaded from dict")
        self._notify_change("dict_load")

    def to_dict(self) -> Dict[str, Any]:
        """导出配置为字典"""
        with self._lock:
            return self._serialize_config(self._config)

    # ── 运行时修改 ───────────────────────────────────────────

    def update_default_mode(self, mode: str) -> None:
        """更新默认模式"""
        with self._lock:
            self._config.default_mode = mode
        logger.info(f"[ConfigManager] default_mode -> {mode}")
        self._notify_change("default_mode")

    def add_slot(self, slot: ModelSlotConfig) -> None:
        """添加模型槽位"""
        with self._lock:
            # 移除同 ID 旧槽位
            self._config.slots = [s for s in self._config.slots if s.slot_id != slot.slot_id]
            self._config.slots.append(slot)
        logger.info(f"[ConfigManager] slot added: {slot.slot_id}")
        self._notify_change("slot_add")

    def remove_slot(self, slot_id: str) -> None:
        """移除模型槽位"""
        with self._lock:
            self._config.slots = [s for s in self._config.slots if s.slot_id != slot_id]
        logger.info(f"[ConfigManager] slot removed: {slot_id}")
        self._notify_change("slot_remove")

    def update_slot(self, slot_id: str, **kwargs) -> bool:
        """更新模型槽位"""
        with self._lock:
            slot = self._config.get_slot(slot_id)
            if not slot:
                return False
            for k, v in kwargs.items():
                if hasattr(slot, k):
                    setattr(slot, k, v)
        logger.info(f"[ConfigManager] slot updated: {slot_id}")
        self._notify_change("slot_update")
        return True

    def enable_slot(self, slot_id: str, enabled: bool = True) -> bool:
        """启用/禁用槽位"""
        return self.update_slot(slot_id, enabled=enabled)

    def switch_model(self, slot_id: str, model_id: str) -> bool:
        """切换槽位的模型"""
        return self.update_slot(slot_id, model_id=model_id)

    def set_ab_test(self, config: ABTestConfig) -> None:
        """设置 A/B 测试"""
        with self._lock:
            self._config.ab_tests = [
                t for t in self._config.ab_tests if t.experiment_id != config.experiment_id
            ]
            self._config.ab_tests.append(config)
        logger.info(f"[ConfigManager] AB test set: {config.experiment_id}")
        self._notify_change("ab_test")

    def remove_ab_test(self, experiment_id: str) -> None:
        """移除 A/B 测试"""
        with self._lock:
            self._config.ab_tests = [
                t for t in self._config.ab_tests if t.experiment_id != experiment_id
            ]
        logger.info(f"[ConfigManager] AB test removed: {experiment_id}")

    def get_active_ab_tests(self) -> List[ABTestConfig]:
        """获取当前活跃的 A/B 测试"""
        now = time.time()
        return [
            t for t in self._config.ab_tests
            if t.enabled
            and (t.start_time is None or t.start_time <= now)
            and (t.end_time is None or t.end_time >= now)
        ]

    # ── 热重载 ───────────────────────────────────────────────

    def start_watch(self, interval: float = 5.0) -> None:
        """启动配置文件监听"""
        if not self._config_path:
            logger.warning("[ConfigManager] no config path, cannot watch")
            return
        if self._watch_thread and self._watch_thread.is_alive():
            return
        self._stop_event.clear()
        self._watch_thread = threading.Thread(
            target=self._watch_loop,
            args=(interval,),
            daemon=True,
            name="config-watch",
        )
        self._watch_thread.start()
        logger.info(f"[ConfigManager] watching {self._config_path} (interval={interval}s)")

    def stop_watch(self) -> None:
        """停止配置文件监听"""
        self._stop_event.set()
        if self._watch_thread:
            self._watch_thread.join(timeout=5.0)
        logger.info("[ConfigManager] watch stopped")

    def _watch_loop(self, interval: float) -> None:
        """监听循环"""
        last_mtime = 0.0
        while not self._stop_event.wait(interval):
            try:
                if not self._config_path or not self._config_path.exists():
                    continue
                mtime = self._config_path.stat().st_mtime
                if mtime > last_mtime:
                    last_mtime = mtime
                    self.load_from_file()
                    logger.info("[ConfigManager] config hot-reloaded")
            except Exception as e:
                logger.debug(f"[ConfigManager] watch error: {e}")

    # ── 序列化/反序列化 ──────────────────────────────────────

    @staticmethod
    def _parse_config(data: Dict[str, Any]) -> ProviderConfig:
        """解析配置字典为 ProviderConfig"""
        config = ProviderConfig(
            default_mode=data.get("default_mode", "local_service"),
            global_params=data.get("global_params", {}),
            hard_load_defaults=data.get("hard_load_defaults", {}),
            local_service_defaults=data.get("local_service_defaults", {}),
            cloud_defaults=data.get("cloud_defaults", {}),
        )

        for slot_data in data.get("slots", []):
            config.slots.append(ModelSlotConfig(
                slot_id=slot_data.get("slot_id", ""),
                model_id=slot_data.get("model_id", ""),
                mode=slot_data.get("mode", "local_service"),
                driver_name=slot_data.get("driver_name", ""),
                params=slot_data.get("params", {}),
                priority=slot_data.get("priority", 100),
                enabled=slot_data.get("enabled", True),
                max_concurrent=slot_data.get("max_concurrent", 1),
                timeout=slot_data.get("timeout", 120.0),
            ))

        for ab_data in data.get("ab_tests", []):
            config.ab_tests.append(ABTestConfig(
                experiment_id=ab_data.get("experiment_id", ""),
                model=ab_data.get("model", ""),
                variants=ab_data.get("variants", {}),
                enabled=ab_data.get("enabled", True),
                start_time=ab_data.get("start_time"),
                end_time=ab_data.get("end_time"),
            ))

        return config

    @staticmethod
    def _serialize_config(config: ProviderConfig) -> Dict[str, Any]:
        """序列化 ProviderConfig 为字典"""
        data = {
            "default_mode": config.default_mode,
            "global_params": config.global_params,
            "hard_load_defaults": config.hard_load_defaults,
            "local_service_defaults": config.local_service_defaults,
            "cloud_defaults": config.cloud_defaults,
            "slots": [
                {
                    "slot_id": s.slot_id,
                    "model_id": s.model_id,
                    "mode": s.mode,
                    "driver_name": s.driver_name,
                    "params": s.params,
                    "priority": s.priority,
                    "enabled": s.enabled,
                    "max_concurrent": s.max_concurrent,
                    "timeout": s.timeout,
                }
                for s in config.slots
            ],
            "ab_tests": [
                {
                    "experiment_id": t.experiment_id,
                    "model": t.model,
                    "variants": t.variants,
                    "enabled": t.enabled,
                    "start_time": t.start_time,
                    "end_time": t.end_time,
                }
                for t in config.ab_tests
            ],
        }
        return data

    # ── 变更通知 ─────────────────────────────────────────────

    def _notify_change(self, reason: str) -> None:
        """触发配置变更通知"""
        if self._on_change:
            try:
                self._on_change(reason, self._config)
            except Exception as e:
                logger.debug(f"[ConfigManager] change callback error: {e}")

    def set_on_change(self, callback: Callable) -> None:
        """设置变更回调"""
        self._on_change = callback

    # ── 便捷方法 ─────────────────────────────────────────────

    @classmethod
    def create_default(cls, output_path: str = "") -> "ProviderConfigManager":
        """创建默认配置"""
        config = ProviderConfig(
            default_mode="local_service",
            hard_load_defaults={
                "n_ctx": 4096,
                "n_gpu_layers": -1,
                "n_threads": 4,
            },
            local_service_defaults={
                "timeout": 120.0,
                "connect_timeout": 10.0,
            },
            cloud_defaults={
                "timeout": 120.0,
                "max_retries": 2,
                "retry_delay": 1.0,
            },
            slots=[
                ModelSlotConfig(
                    slot_id="local-default",
                    model_id="",
                    mode="local_service",
                    driver_name="local_service",
                    params={"base_url": "http://localhost:11434"},
                    priority=100,
                ),
                ModelSlotConfig(
                    slot_id="cloud-default",
                    model_id="",
                    mode="cloud_service",
                    driver_name="cloud",
                    params={"provider": "deepseek"},
                    priority=50,
                ),
            ],
        )
        mgr = cls(config_path=output_path if output_path else None)
        mgr._config = config
        if output_path:
            mgr.save_to_file(output_path)
        return mgr
