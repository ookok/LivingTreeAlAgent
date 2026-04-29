"""
积分注册表 (Credit Registry)
=============================

维护插件和用户的积分消耗模型、能力画像。

内部数据库结构：
{
    "nllb_local": {
        "type": "plugin",
        "credit_model": {
            "base": 0,
            "cpu_per_sec": 1,      # 每秒CPU消耗1积分
            "mem_per_mb": 0.1      # 每MB内存消耗0.1积分
        },
        "capability": {
            "task_type": "translation",
            "quality_score": 70,
            "avg_time_sec_per_kchar": 30,
            "max_input_length": 5000
        }
    },
    "deepseek_api": {
        "type": "external_api",
        "credit_model": {
            "per_kchar": 50,       # 每千字50积分
            "request_fee": 0
        },
        "capability": {
            "task_type": "translation",
            "quality_score": 85,
            "avg_time_sec_per_kchar": 2,
            "max_input_length": 32000
        }
    }
}
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import json
import time
from threading import RLock


class PluginType(Enum):
    """插件类型"""
    LOCAL_PLUGIN = "local_plugin"          # 本地插件
    EXTERNAL_API = "external_api"          # 外部API
    HYBRID = "hybrid"                      # 混合型


class TaskType(Enum):
    """任务类型"""
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    CODE_GENERATION = "code_generation"
    IMAGE_PROCESSING = "image_processing"
    AUDIO_PROCESSING = "audio_processing"
    TEXT_ANALYSIS = "text_analysis"
    KNOWLEDGE_QUERY = "knowledge_query"
    FILE_CONVERSION = "file_conversion"
    CUSTOM = "custom"


@dataclass
class CreditModel:
    """积分消耗模型"""
    base: float = 0.0                      # 基础消耗
    cpu_per_sec: float = 0.0              # 每秒CPU消耗
    mem_per_mb: float = 0.0               # 每MB内存消耗
    per_kchar: float = 0.0                 # 每千字符消耗（API类）
    per_request: float = 0.0               # 每次请求消耗
    network_per_kb: float = 0.0            # 每KB网络传输消耗


@dataclass
class Capability:
    """插件能力"""
    task_type: TaskType = TaskType.CUSTOM
    quality_score: int = 70               # 质量分数 0-100
    avg_time_sec_per_kchar: float = 1.0    # 平均处理速度（秒/千字符）
    max_input_length: int = 10000          # 最大输入长度
    supports_batch: bool = False            # 支持批量处理
    parallel_instances: int = 1             # 最大并行实例数


@dataclass
class RegionLatency:
    """地域延迟配置（南京本地化）"""
    region: str = "default"                # 地域标识
    base_latency_ms: float = 0.0           # 基础延迟（毫秒）
    credit_per_ms: float = 0.01            # 每毫秒延迟消耗积分


@dataclass
class ComplianceConstraint:
    """合规约束"""
    required: bool = False                 # 是否强制要求
    allowed_plugins: List[str] = field(default_factory=list)  # 允许使用的插件列表
    blocked_plugins: List[str] = field(default_factory=list)  # 禁止使用的插件列表
    reason: str = ""                       # 约束原因


@dataclass
class PluginCreditProfile:
    """插件积分配置画像"""
    plugin_id: str
    name: str
    plugin_type: PluginType
    credit_model: CreditModel
    capability: Capability
    region_latency: List[RegionLatency] = field(default_factory=list)
    compliance: ComplianceConstraint = field(default_factory=ComplianceConstraint)
    enabled: bool = True
    tags: List[str] = field(default_factory=list)  # 标签：["免费", "高速", "高质量"]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "plugin_type": self.plugin_type.value,
            "credit_model": {
                "base": self.credit_model.base,
                "cpu_per_sec": self.credit_model.cpu_per_sec,
                "mem_per_mb": self.credit_model.mem_per_mb,
                "per_kchar": self.credit_model.per_kchar,
                "per_request": self.credit_model.per_request,
                "network_per_kb": self.credit_model.network_per_kb,
            },
            "capability": {
                "task_type": self.capability.task_type.value,
                "quality_score": self.capability.quality_score,
                "avg_time_sec_per_kchar": self.capability.avg_time_sec_per_kchar,
                "max_input_length": self.capability.max_input_length,
                "supports_batch": self.capability.supports_batch,
                "parallel_instances": self.capability.parallel_instances,
            },
            "region_latency": [
                {"region": r.region, "base_latency_ms": r.base_latency_ms, "credit_per_ms": r.credit_per_ms}
                for r in self.region_latency
            ],
            "compliance": {
                "required": self.compliance.required,
                "allowed_plugins": self.compliance.allowed_plugins,
                "blocked_plugins": self.compliance.blocked_plugins,
                "reason": self.compliance.reason,
            },
            "enabled": self.enabled,
            "tags": self.tags,
        }


@dataclass
class UserCreditProfile:
    """用户积分配置"""
    user_id: str
    total_credits: float = 10000.0         # 总积分
    time_value_per_hour: float = 200.0     # 用户时间价值（积分/小时）
    quality_preference: int = 80           # 质量偏好 0-100
    max_wait_time_sec: float = 30.0        # 最大等待时间（秒）
    budget_per_task: float = 500.0         # 单任务预算
    daily_budget: float = 5000.0           # 每日预算
    compliance_mode: bool = True           # 合规模式
    learning_enabled: bool = True          # 启用学习优化
    preferred_plugins: List[str] = field(default_factory=list)  # 偏好插件
    blocked_plugins: List[str] = field(default_factory=list)     # 屏蔽插件

    @property
    def time_value_per_sec(self) -> float:
        """每秒时间价值积分"""
        return self.time_value_per_hour / 3600


class CreditRegistry:
    """
    积分注册表 - 维护所有插件和用户的积分配置

    核心功能：
    1. 插件注册与管理
    2. 用户配置管理
    3. 能力查询
    4. 积分模型计算
    """

    _instance = None
    _lock = RLock()

    def __new__(cls):
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

        # 插件注册表
        self._plugins: Dict[str, PluginCreditProfile] = {}

        # 用户配置表
        self._users: Dict[str, UserCreditProfile] = {}

        # 默认用户配置
        self._default_user = UserCreditProfile(user_id="default")

        # 观察者回调
        self._observers: Dict[str, List[Callable]] = {}

        # 历史记录
        self._plugin_history: Dict[str, List[Dict]] = {}

    @classmethod
    def get_instance(cls) -> 'CreditRegistry':
        """获取单例"""
        return cls()

    # ==================== 插件管理 ====================

    def register_plugin(self, profile: PluginCreditProfile) -> None:
        """
        注册插件

        Args:
            profile: 插件积分配置
        """
        with self._lock:
            self._plugins[profile.plugin_id] = profile
            self._plugin_history[profile.plugin_id] = []
            self._notify_observers("plugin_registered", profile)

    def unregister_plugin(self, plugin_id: str) -> bool:
        """注销插件"""
        with self._lock:
            if plugin_id in self._plugins:
                del self._plugins[plugin_id]
                self._notify_observers("plugin_unregistered", plugin_id)
                return True
            return False

    def get_plugin(self, plugin_id: str) -> Optional[PluginCreditProfile]:
        """获取插件配置"""
        return self._plugins.get(plugin_id)

    def list_plugins(
        self,
        task_type: Optional[TaskType] = None,
        enabled_only: bool = True,
        min_quality: int = 0
    ) -> List[PluginCreditProfile]:
        """
        列出插件

        Args:
            task_type: 任务类型过滤
            enabled_only: 仅启用状态
            min_quality: 最低质量分数

        Returns:
            符合条件的插件列表
        """
        result = []
        for plugin in self._plugins.values():
            if enabled_only and not plugin.enabled:
                continue
            if task_type and plugin.capability.task_type != task_type:
                continue
            if plugin.capability.quality_score < min_quality:
                continue
            result.append(plugin)
        return result

    def enable_plugin(self, plugin_id: str) -> bool:
        """启用插件"""
        plugin = self._plugins.get(plugin_id)
        if plugin:
            plugin.enabled = True
            return True
        return False

    def disable_plugin(self, plugin_id: str) -> bool:
        """禁用插件"""
        plugin = self._plugins.get(plugin_id)
        if plugin:
            plugin.enabled = False
            return True
        return False

    # ==================== 用户管理 ====================

    def register_user(self, profile: UserCreditProfile) -> None:
        """注册用户配置"""
        with self._lock:
            self._users[profile.user_id] = profile

    def get_user(self, user_id: str = "default") -> UserCreditProfile:
        """获取用户配置"""
        return self._users.get(user_id, self._default_user)

    def update_user_credits(self, user_id: str, delta: float) -> float:
        """
        更新用户积分

        Returns:
            新的积分余额
        """
        user = self.get_user(user_id)
        user.total_credits = max(0, user.total_credits + delta)
        return user.total_credits

    def set_user_time_value(self, user_id: str, credits_per_hour: float) -> None:
        """设置用户时间价值"""
        user = self.get_user(user_id)
        user.time_value_per_hour = credits_per_hour

    # ==================== 预置插件 ====================

    def register_preset_plugins(self) -> None:
        """注册预置插件（南京本地化场景）"""

        # NLLB本地翻译模型
        self.register_plugin(PluginCreditProfile(
            plugin_id="nllb_local",
            name="本地NLLB翻译",
            plugin_type=PluginType.LOCAL_PLUGIN,
            credit_model=CreditModel(
                base=0,
                cpu_per_sec=10,          # 每秒10积分
                mem_per_mb=1            # 每MB内存1积分
            ),
            capability=Capability(
                task_type=TaskType.TRANSLATION,
                quality_score=70,
                avg_time_sec_per_kchar=30,
                max_input_length=5000
            ),
            tags=["免费", "本地", "隐私保护"]
        ))

        # DeepSeek API
        self.register_plugin(PluginCreditProfile(
            plugin_id="deepseek_api",
            name="DeepSeek翻译API",
            plugin_type=PluginType.EXTERNAL_API,
            credit_model=CreditModel(
                base=0,
                per_kchar=50            # 每千字50积分
            ),
            capability=Capability(
                task_type=TaskType.TRANSLATION,
                quality_score=85,
                avg_time_sec_per_kchar=2,
                max_input_length=32000
            ),
            region_latency=[
                RegionLatency(region="beijing", base_latency_ms=50, credit_per_ms=0.5),
                RegionLatency(region="shanghai", base_latency_ms=30, credit_per_ms=0.3),
            ],
            tags=["高速", "高质量"]
        ))

        # GPT-4 API
        self.register_plugin(PluginCreditProfile(
            plugin_id="gpt4_api",
            name="GPT-4翻译API",
            plugin_type=PluginType.EXTERNAL_API,
            credit_model=CreditModel(
                base=0,
                per_kchar=200           # 每千字200积分
            ),
            capability=Capability(
                task_type=TaskType.TRANSLATION,
                quality_score=95,
                avg_time_sec_per_kchar=1,
                max_input_length=128000
            ),
            region_latency=[
                RegionLatency(region="beijing", base_latency_ms=80, credit_per_ms=0.8),
                RegionLatency(region="shanghai", base_latency_ms=60, credit_per_ms=0.6),
            ],
            tags=["最高质量", "极速"]
        ))

        # 内部GPU服务器（零边际成本资源）
        self.register_plugin(PluginCreditProfile(
            plugin_id="internal_gpu",
            name="内部GPU服务器",
            plugin_type=PluginType.LOCAL_PLUGIN,
            credit_model=CreditModel(
                base=0,
                cpu_per_sec=5,          # 内部成本极低
                mem_per_mb=0.5
            ),
            capability=Capability(
                task_type=TaskType.TRANSLATION,
                quality_score=80,
                avg_time_sec_per_kchar=5,
                max_input_length=20000
            ),
            tags=["免费", "内部", "高速"]
        ))

        # OCR识别插件
        self.register_plugin(PluginCreditProfile(
            plugin_id="ocr_local",
            name="本地OCR识别",
            plugin_type=PluginType.LOCAL_PLUGIN,
            credit_model=CreditModel(
                base=0,
                cpu_per_sec=8,
                mem_per_mb=2
            ),
            capability=Capability(
                task_type=TaskType.TEXT_ANALYSIS,
                quality_score=75,
                avg_time_sec_per_kchar=10,
                max_input_length=10000
            ),
            tags=["免费", "本地"]
        ))

        # 语音识别插件
        self.register_plugin(PluginCreditProfile(
            plugin_id="whisper_api",
            name="Whisper语音识别API",
            plugin_type=PluginType.EXTERNAL_API,
            credit_model=CreditModel(
                base=0,
                per_kchar=30
            ),
            capability=Capability(
                task_type=TaskType.AUDIO_PROCESSING,
                quality_score=90,
                avg_time_sec_per_kchar=1,
                max_input_length=500000
            ),
            tags=["高质量", "语音"]
        ))

    # ==================== 观察者模式 ====================

    def add_observer(self, event_type: str, callback: Callable) -> None:
        """添加观察者"""
        if event_type not in self._observers:
            self._observers[event_type] = []
        self._observers[event_type].append(callback)

    def _notify_observers(self, event_type: str, data: Any) -> None:
        """通知观察者"""
        for callback in self._observers.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                print(f"Observer callback error: {e}")

    # ==================== 历史记录 ====================

    def record_usage(self, plugin_id: str, usage_data: Dict) -> None:
        """记录插件使用历史"""
        if plugin_id in self._plugin_history:
            self._plugin_history[plugin_id].append({
                "timestamp": time.time(),
                **usage_data
            })
            # 保留最近100条
            if len(self._plugin_history[plugin_id]) > 100:
                self._plugin_history[plugin_id] = self._plugin_history[plugin_id][-100:]

    def get_plugin_history(self, plugin_id: str, limit: int = 10) -> List[Dict]:
        """获取插件使用历史"""
        history = self._plugin_history.get(plugin_id, [])
        return history[-limit:]

    # ==================== 序列化 ====================

    def to_json(self) -> str:
        """导出为JSON"""
        data = {
            "plugins": {pid: p.to_dict() for pid, p in self._plugins.items()},
            "users": {
                uid: {
                    "total_credits": u.total_credits,
                    "time_value_per_hour": u.time_value_per_hour,
                    "quality_preference": u.quality_preference,
                    "max_wait_time_sec": u.max_wait_time_sec,
                    "budget_per_task": u.budget_per_task,
                    "daily_budget": u.daily_budget,
                }
                for uid, u in self._users.items()
            }
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'CreditRegistry':
        """从JSON加载"""
        data = json.loads(json_str)
        registry = cls()
        # 重建插件
        for pid, pdata in data.get("plugins", {}).items():
            capability = Capability(
                task_type=TaskType(pdata["capability"]["task_type"]),
                quality_score=pdata["capability"]["quality_score"],
                avg_time_sec_per_kchar=pdata["capability"]["avg_time_sec_per_kchar"],
                max_input_length=pdata["capability"]["max_input_length"],
                supports_batch=pdata["capability"].get("supports_batch", False),
                parallel_instances=pdata["capability"].get("parallel_instances", 1),
            )
            credit_model = CreditModel(**pdata["credit_model"])
            profile = PluginCreditProfile(
                plugin_id=pid,
                name=pdata["name"],
                plugin_type=PluginType(pdata["plugin_type"]),
                credit_model=credit_model,
                capability=capability,
                enabled=pdata.get("enabled", True),
                tags=pdata.get("tags", []),
            )
            registry.register_plugin(profile)
        return registry


def get_credit_registry() -> CreditRegistry:
    """获取积分注册表单例"""
    return CreditRegistry.get_instance()
