"""
积分注册表 (Credit Registry) — 插件和用户的积分系统

合并增强自:
- client/src/business/credit_economy/credit_registry.py
- client/src/business/credit_economy/scheduler.py

增强:
- 统一类型系统（PluginType, TaskType, DataFormat）
- 观察者模式事件系统
- 线程安全（RLock）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import time
from threading import RLock


# ============================================================================
# 枚举
# ============================================================================

class PluginType(Enum):
    LOCAL_PLUGIN = "local_plugin"
    EXTERNAL_API = "external_api"
    HYBRID = "hybrid"


class TaskType(Enum):
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    CODE_GENERATION = "code_generation"
    IMAGE_PROCESSING = "image_processing"
    AUDIO_PROCESSING = "audio_processing"
    TEXT_ANALYSIS = "text_analysis"
    KNOWLEDGE_QUERY = "knowledge_query"
    FILE_CONVERSION = "file_conversion"
    CUSTOM = "custom"


class DataFormat(Enum):
    TEXT = "text"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    PDF = "pdf"
    BINARY = "binary"


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class CreditModel:
    """积分消耗模型"""
    base: float = 0.0
    cpu_per_sec: float = 0.0
    mem_per_mb: float = 0.0
    per_kchar: float = 0.0
    per_request: float = 0.0
    network_per_kb: float = 0.0


@dataclass
class Capability:
    """插件能力画像"""
    task_type: TaskType = TaskType.CUSTOM
    quality_score: int = 70
    avg_time_sec_per_kchar: float = 1.0
    max_input_length: int = 10000
    supports_batch: bool = False
    parallel_instances: int = 1


@dataclass
class RegionLatency:
    """地域延迟配置"""
    region: str = "default"
    base_latency_ms: float = 0.0
    credit_per_ms: float = 0.01


@dataclass
class ComplianceConstraint:
    """合规约束"""
    required: bool = False
    allowed_plugins: List[str] = field(default_factory=list)
    blocked_plugins: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class PluginCreditProfile:
    """插件完整积分画像"""
    plugin_id: str = ""
    name: str = ""
    plugin_type: PluginType = PluginType.LOCAL_PLUGIN
    credit_model: CreditModel = field(default_factory=CreditModel)
    capability: Capability = field(default_factory=Capability)
    region_latency: RegionLatency = field(default_factory=RegionLatency)
    compliance: ComplianceConstraint = field(default_factory=ComplianceConstraint)
    enabled: bool = True
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "plugin_type": self.plugin_type.value,
            "enabled": self.enabled,
            "capability": {
                "task_type": self.capability.task_type.value,
                "quality_score": self.capability.quality_score,
            },
            "tags": self.tags,
        }


@dataclass
class UserCreditProfile:
    """用户积分配置"""
    user_id: str = ""
    total_credits: float = 1000.0
    time_value_per_hour: float = 10.0
    quality_preference: int = 70
    max_wait_time_sec: float = 60.0
    budget_per_task: float = 100.0
    daily_budget: float = 500.0
    compliance_mode: bool = False
    learning_enabled: bool = True
    preferred_plugins: List[str] = field(default_factory=list)
    blocked_plugins: List[str] = field(default_factory=list)

    @property
    def time_value_per_sec(self) -> float:
        return self.time_value_per_hour / 3600.0


@dataclass
class TaskSpec:
    """任务规格"""
    task_id: str = ""
    task_type: TaskType = TaskType.CUSTOM
    input_length: int = 0
    input_data: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    min_quality: int = 60
    max_wait_time: float = 60.0
    budget: float = 1000.0
    preferred_region: str = "default"
    is_compliance_required: bool = False
    tags: List[str] = field(default_factory=list)

    @property
    def length_kchar(self) -> float:
        return self.input_length / 1000.0


@dataclass
class EstimationResult:
    """成本估算结果"""
    plugin_id: str = ""
    plugin_name: str = ""
    task_id: str = ""
    direct_credits: float = 0.0
    base_cost: float = 0.0
    cpu_cost: float = 0.0
    mem_cost: float = 0.0
    api_cost: float = 0.0
    network_cost: float = 0.0
    estimated_time_sec: float = 0.0
    time_credits: float = 0.0
    region_latency_ms: float = 0.0
    quality_score: int = 0
    total_credits: float = 0.0
    is_viable: bool = True
    viability_reason: str = ""


# ============================================================================
# 积分注册表
# ============================================================================

class CreditRegistry:
    """积分注册表（单例，线程安全）"""

    _instance: Optional[CreditRegistry] = None
    _lock = RLock()

    def __new__(cls) -> CreditRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._plugins: Dict[str, PluginCreditProfile] = {}
        self._users: Dict[str, UserCreditProfile] = {}
        self._observers: Dict[str, List[Callable]] = {
            "plugin_registered": [],
            "plugin_updated": [],
            "plugin_removed": [],
            "user_updated": [],
        }
        self._register_preset_plugins()

    # ========================================================================
    # 插件管理
    # ========================================================================

    def register_plugin(self, profile: PluginCreditProfile) -> None:
        with self._lock:
            is_new = profile.plugin_id not in self._plugins
            self._plugins[profile.plugin_id] = profile
            event = "plugin_registered" if is_new else "plugin_updated"
            self._notify(event, profile)

    def unregister_plugin(self, plugin_id: str) -> None:
        with self._lock:
            if plugin_id in self._plugins:
                profile = self._plugins.pop(plugin_id)
                self._notify("plugin_removed", profile)

    def get_plugin(self, plugin_id: str) -> Optional[PluginCreditProfile]:
        return self._plugins.get(plugin_id)

    def list_plugins(
        self,
        task_type: Optional[TaskType] = None,
        enabled_only: bool = True,
        min_quality: int = 0,
    ) -> List[PluginCreditProfile]:
        result = list(self._plugins.values())
        if enabled_only:
            result = [p for p in result if p.enabled]
        if task_type:
            result = [p for p in result if p.capability.task_type == task_type]
        if min_quality > 0:
            result = [p for p in result if p.capability.quality_score >= min_quality]
        return result

    def enable_plugin(self, plugin_id: str) -> bool:
        p = self.get_plugin(plugin_id)
        if p:
            p.enabled = True
            self._notify("plugin_updated", p)
            return True
        return False

    def disable_plugin(self, plugin_id: str) -> bool:
        p = self.get_plugin(plugin_id)
        if p:
            p.enabled = False
            self._notify("plugin_updated", p)
            return True
        return False

    # ========================================================================
    # 用户管理
    # ========================================================================

    def register_user(self, profile: UserCreditProfile) -> None:
        with self._lock:
            self._users[profile.user_id] = profile

    def get_user(self, user_id: str) -> Optional[UserCreditProfile]:
        return self._users.get(user_id)

    def update_user_credits(self, user_id: str, delta: float) -> bool:
        user = self.get_user(user_id)
        if user:
            user.total_credits = max(0.0, user.total_credits + delta)
            self._notify("user_updated", user)
            return True
        return False

    # ========================================================================
    # 成本估算
    # ========================================================================

    def estimate_cost(
        self,
        plugin_id: str,
        task: TaskSpec,
        user: Optional[UserCreditProfile] = None,
    ) -> EstimationResult:
        """估算单个插件执行任务的成本"""
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return EstimationResult(
                plugin_id=plugin_id,
                task_id=task.task_id,
                is_viable=False,
                viability_reason="Plugin not found",
            )

        model = plugin.credit_model
        cap = plugin.capability

        # 直接积分消耗
        base_cost = model.base
        cpu_cost = model.cpu_per_sec * cap.avg_time_sec_per_kchar * task.length_kchar
        mem_cost = model.mem_per_mb * 10  # 假设10MB
        api_cost = model.per_kchar * task.length_kchar
        network_cost = model.network_per_kb * task.input_length / 1024.0

        direct = base_cost + cpu_cost + mem_cost + api_cost + network_cost

        # 时间成本
        estimated_time = cap.avg_time_sec_per_kchar * task.length_kchar
        region_latency = plugin.region_latency.base_latency_ms
        time_cost = 0.0
        if user:
            time_cost = estimated_time * user.time_value_per_sec

        total = direct + time_cost

        # 可行性检查
        viable = True
        reasons = []
        if task.min_quality > 0 and cap.quality_score < task.min_quality:
            viable = False
            reasons.append(f"Quality {cap.quality_score} < required {task.min_quality}")
        if task.budget > 0 and total > task.budget:
            viable = False
            reasons.append(f"Cost {total:.1f} > budget {task.budget:.1f}")
        if estimated_time > task.max_wait_time:
            viable = False
            reasons.append(f"Time {estimated_time:.1f}s > max {task.max_wait_time}s")

        return EstimationResult(
            plugin_id=plugin_id,
            plugin_name=plugin.name,
            task_id=task.task_id,
            direct_credits=direct,
            base_cost=base_cost,
            cpu_cost=cpu_cost,
            mem_cost=mem_cost,
            api_cost=api_cost,
            network_cost=network_cost,
            estimated_time_sec=estimated_time,
            time_credits=time_cost,
            region_latency_ms=region_latency,
            quality_score=cap.quality_score,
            total_credits=total,
            is_viable=viable,
            viability_reason="; ".join(reasons),
        )

    def find_best_plugin(
        self,
        task: TaskSpec,
        user: Optional[UserCreditProfile] = None,
    ) -> Optional[EstimationResult]:
        """找到最优插件（综合考虑质量、成本、时间）"""
        candidates = self.list_plugins(task_type=task.task_type, enabled_only=True)

        best: Optional[EstimationResult] = None
        best_score = -1.0

        for plugin in candidates:
            est = self.estimate_cost(plugin.plugin_id, task, user)
            if not est.is_viable:
                continue

            # 综合评分：质量优先，但也要考虑成本
            quality_weight = 0.5
            cost_weight = 0.3
            time_weight = 0.2

            quality_norm = est.quality_score / 100.0
            cost_norm = max(0, 1.0 - est.total_credits / max(task.budget, 1.0))
            time_norm = max(0, 1.0 - est.estimated_time_sec / max(task.max_wait_time, 1.0))

            score = (quality_weight * quality_norm
                     + cost_weight * cost_norm
                     + time_weight * time_norm)

            if score > best_score:
                best_score = score
                best = est

        return best

    # ========================================================================
    # 预设插件
    # ========================================================================

    def _register_preset_plugins(self) -> None:
        """注册预设插件"""
        presets = [
            PluginCreditProfile(
                plugin_id="nllb_local",
                name="NLLB 本地翻译",
                plugin_type=PluginType.LOCAL_PLUGIN,
                credit_model=CreditModel(cpu_per_sec=1.0, mem_per_mb=0.1),
                capability=Capability(
                    task_type=TaskType.TRANSLATION,
                    quality_score=70,
                    avg_time_sec_per_kchar=30.0,
                    max_input_length=5000,
                ),
            ),
            PluginCreditProfile(
                plugin_id="deepseek_api",
                name="DeepSeek API",
                plugin_type=PluginType.EXTERNAL_API,
                credit_model=CreditModel(per_kchar=50.0),
                capability=Capability(
                    task_type=TaskType.TRANSLATION,
                    quality_score=85,
                    avg_time_sec_per_kchar=2.0,
                    max_input_length=32000,
                    supports_batch=True,
                ),
                region_latency=RegionLatency(
                    region="cn-east",
                    base_latency_ms=200.0,
                ),
            ),
            PluginCreditProfile(
                plugin_id="ollama_local",
                name="Ollama 本地模型",
                plugin_type=PluginType.LOCAL_PLUGIN,
                credit_model=CreditModel(base=5.0, cpu_per_sec=2.0, mem_per_mb=0.2),
                capability=Capability(
                    task_type=TaskType.TEXT_ANALYSIS,
                    quality_score=75,
                    avg_time_sec_per_kchar=5.0,
                    max_input_length=8000,
                ),
            ),
            PluginCreditProfile(
                plugin_id="openai_api",
                name="OpenAI API",
                plugin_type=PluginType.EXTERNAL_API,
                credit_model=CreditModel(per_kchar=100.0, per_request=10.0),
                capability=Capability(
                    task_type=TaskType.CODE_GENERATION,
                    quality_score=95,
                    avg_time_sec_per_kchar=1.0,
                    max_input_length=128000,
                    supports_batch=True,
                ),
                region_latency=RegionLatency(
                    region="us-east",
                    base_latency_ms=500.0,
                ),
            ),
        ]

        for p in presets:
            self.register_plugin(p)

    # ========================================================================
    # 观察者模式
    # ========================================================================

    def on(self, event: str, callback: Callable) -> None:
        if event in self._observers:
            self._observers[event].append(callback)

    def _notify(self, event: str, data: Any) -> None:
        for cb in self._observers.get(event, []):
            try:
                cb(data)
            except Exception:
                pass


# 单例获取
def get_credit_registry() -> CreditRegistry:
    return CreditRegistry()
