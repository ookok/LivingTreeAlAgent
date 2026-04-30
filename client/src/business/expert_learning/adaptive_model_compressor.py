"""
自适应模型压缩 (Adaptive Model Compression)
============================================

根据用户使用频率动态调整模型能力：
- 高频领域 → 保留/增强完整能力
- 低频领域 → 压缩/卸载
- 新领域 → 按需学习

核心原理：
不是通用压缩，而是针对个人使用习惯的压缩。
"""

import time
import threading
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import statistics
import json
from pathlib import Path
from business.logger import get_logger
logger = get_logger('expert_learning.adaptive_model_compressor')


# ── 领域能力等级 ─────────────────────────────────────────────────────────────

class CapabilityLevel(Enum):
    """能力等级"""
    FULL = "full"           # 完整能力
    STANDARD = "standard"   # 标准能力
    COMPRESSED = "compressed"  # 压缩能力
    OFFLOADED = "offloaded"   # 已卸载（按需加载）


# ── 领域配置 ─────────────────────────────────────────────────────────────────

@dataclass
class DomainCapability:
    """领域能力配置"""
    domain: str
    level: CapabilityLevel = CapabilityLevel.FULL

    # 使用统计
    request_count: int = 0
    last_used: float = 0
    avg_latency_ms: float = 0

    # 质量指标
    success_rate: float = 0.0
    correction_rate: float = 0.0
    user_rating: float = 0.0  # 如果有反馈

    # 能力参数
    max_context_tokens: int = 4096
    model_size: str = "3b"    # 推荐的模型大小
    quantization: str = "q4"   # 量化级别

    # 压缩配置
    compression_ratio: float = 1.0  # 1.0 = 不压缩
    priority: int = 5  # 1-10, 10=最高优先级


@dataclass
class DomainStats:
    """领域统计数据"""
    domain: str
    total_requests: int = 0
    successful_requests: int = 0
    expert_calls: int = 0
    local_calls: int = 0
    cache_hits: int = 0
    corrections: int = 0
    total_latency_ms: float = 0
    timestamps: List[float] = field(default_factory=list)

    @property
    def avg_latency(self) -> float:
        return self.total_latency_ms / max(1, self.total_requests)

    @property
    def success_rate(self) -> float:
        return self.successful_requests / max(1, self.total_requests)

    @property
    def expert_rate(self) -> float:
        return self.expert_calls / max(1, self.total_requests)

    @property
    def cache_rate(self) -> float:
        return self.cache_hits / max(1, self.total_requests)


# ── 自适应压缩器 ─────────────────────────────────────────────────────────────

class AdaptiveModelCompressor:
    """
    自适应模型压缩器

    根据个人使用频率自动调整模型能力分布

    使用示例:
    ```python
    compressor = AdaptiveModelCompressor()

    # 记录请求
    compressor.record_request(
        domain="编程",
        latency_ms=150,
        success=True,
        used_expert=False
    )

    # 获取压缩建议
    plan = compressor.get_compression_plan()
    logger.info(f"建议: {plan['recommendations']}")

    # 应用压缩
    compressor.apply_compression(plan)
    ```
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        auto_adjust: bool = True
    ):
        self._lock = threading.RLock()

        self._data_dir = data_dir or Path.home() / ".hermes-desktop" / "model_compression"
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._auto_adjust = auto_adjust

        # 领域配置
        self._domains: Dict[str, DomainCapability] = {}
        self._domain_stats: Dict[str, DomainStats] = defaultdict(lambda: DomainStats(domain=""))

        # 全局统计
        self._total_requests = 0
        self._start_time = time.time()

        # 能力分布
        self._capability_distribution = {
            CapabilityLevel.FULL: [],
            CapabilityLevel.STANDARD: [],
            CapabilityLevel.COMPRESSED: [],
            CapabilityLevel.OFFLOADED: []
        }

        # 预设领域
        self._init_default_domains()

        # 加载历史配置
        self._load_config()

        logger.info("[AdaptiveCompressor] Initialized")

    def _init_default_domains(self):
        """初始化默认领域配置"""
        default_domains = [
            # 高频通用领域
            {"domain": "闲聊", "level": CapabilityLevel.FULL, "priority": 8},
            {"domain": "问答", "level": CapabilityLevel.FULL, "priority": 9},
            {"domain": "搜索", "level": CapabilityLevel.FULL, "priority": 8},

            # 专业领域
            {"domain": "编程", "level": CapabilityLevel.STANDARD, "priority": 7},
            {"domain": "写作", "level": CapabilityLevel.STANDARD, "priority": 7},
            {"domain": "翻译", "level": CapabilityLevel.STANDARD, "priority": 6},
            {"domain": "分析", "level": CapabilityLevel.STANDARD, "priority": 7},

            # 专业深度领域
            {"domain": "数学", "level": CapabilityLevel.COMPRESSED, "priority": 4},
            {"domain": "法律", "level": CapabilityLevel.COMPRESSED, "priority": 3},
            {"domain": "医学", "level": CapabilityLevel.COMPRESSED, "priority": 3},
            {"domain": "金融", "level": CapabilityLevel.COMPRESSED, "priority": 4},

            # 低频领域
            {"domain": "其他", "level": CapabilityLevel.OFFLOADED, "priority": 2},
        ]

        for d in default_domains:
            self._domains[d["domain"]] = DomainCapability(
                domain=d["domain"],
                level=d["level"],
                priority=d["priority"]
            )

    def record_request(
        self,
        domain: str,
        latency_ms: float,
        success: bool = True,
        used_expert: bool = False,
        cache_hit: bool = False,
        corrected: bool = False,
        intent: Optional[str] = None
    ):
        """记录领域请求"""
        with self._lock:
            self._total_requests += 1

            # 确保领域存在
            if domain not in self._domains:
                self._domains[domain] = DomainCapability(domain=domain)
                self._domain_stats[domain] = DomainStats(domain=domain)

            # 更新能力配置
            cap = self._domains[domain]
            cap.request_count += 1
            cap.last_used = time.time()

            # 更新统计
            stats = self._domain_stats[domain]
            stats.total_requests += 1
            stats.total_latency_ms += latency_ms
            stats.timestamps.append(time.time())

            if success:
                stats.successful_requests += 1
            if used_expert:
                stats.expert_calls += 1
            if cache_hit:
                stats.cache_hits += 1
            if corrected:
                stats.corrections += 1

            # 保持时间戳在合理范围
            if len(stats.timestamps) > 1000:
                stats.timestamps = stats.timestamps[-500:]

            # 根据使用频率自动调整能力
            if self._auto_adjust:
                self._adjust_capability(domain)

            # 保存配置
            self._save_config()

    def _adjust_capability(self, domain: str):
        """根据使用频率调整能力"""
        cap = self._domains[domain]
        stats = self._domain_stats[domain]

        # 计算使用频率 (最近7天)
        now = time.time()
        recent_requests = sum(
            1 for ts in stats.timestamps
            if now - ts < 7 * 24 * 3600
        )

        # 高频领域 → 提升能力
        if recent_requests > 50:
            if cap.level == CapabilityLevel.COMPRESSED:
                cap.level = CapabilityLevel.STANDARD
                logger.info(f"[Compressor] {domain}: COMPRESSED -> STANDARD (高频)")
            elif cap.level == CapabilityLevel.OFFLOADED:
                cap.level = CapabilityLevel.COMPRESSED
                logger.info(f"[Compressor] {domain}: OFFLOADED -> COMPRESSED (使用增加)")

        # 超高频领域 → 完整能力
        if recent_requests > 200:
            if cap.level in [CapabilityLevel.STANDARD, CapabilityLevel.COMPRESSED]:
                cap.level = CapabilityLevel.FULL
                logger.info(f"[Compressor] {domain}: -> FULL (超高频)")

        # 低频领域 → 压缩能力
        elif recent_requests < 5 and cap.request_count > 20:
            if cap.level == CapabilityLevel.FULL:
                cap.level = CapabilityLevel.STANDARD
                logger.info(f"[Compressor] {domain}: FULL -> STANDARD (低频)")

        # 更新能力参数
        self._update_capability_params(cap, recent_requests)

    def _update_capability_params(self, cap: DomainCapability, recent_requests: int):
        """根据频率更新能力参数"""
        # 模型大小和量化级别
        if recent_requests > 100:  # 高频
            cap.model_size = "7b"
            cap.quantization = "q4"
            cap.compression_ratio = 1.0
            cap.max_context_tokens = 8192
        elif recent_requests > 20:  # 中频
            cap.model_size = "3b"
            cap.quantization = "q4"
            cap.compression_ratio = 0.8
            cap.max_context_tokens = 4096
        elif recent_requests > 5:  # 低频
            cap.model_size = "1b"
            cap.quantization = "q4"
            cap.compression_ratio = 0.5
            cap.max_context_tokens = 2048
        else:  # 极低频
            cap.model_size = "0.5b"
            cap.quantization = "q8"
            cap.compression_ratio = 0.3
            cap.max_context_tokens = 1024

    def get_compression_plan(self) -> Dict[str, Any]:
        """
        获取压缩计划

        返回建议的调整方案
        """
        with self._lock:
            plan = {
                "timestamp": time.time(),
                "total_requests": self._total_requests,
                "active_domains": len([d for d in self._domains.values() if d.request_count > 0]),
                "recommendations": [],
                "domain_status": {},
                "capability_summary": {}
            }

            # 按优先级排序
            sorted_domains = sorted(
                self._domains.items(),
                key=lambda x: (
                    x[1].priority,
                    x[1].request_count,
                    x[1].last_used
                ),
                reverse=True
            )

            # 领域状态
            for domain, cap in sorted_domains:
                stats = self._domain_stats.get(domain, DomainStats(domain=domain))

                status = {
                    "level": cap.level.value,
                    "priority": cap.priority,
                    "requests": cap.request_count,
                    "recent_requests_7d": sum(
                        1 for ts in stats.timestamps
                        if time.time() - ts < 7 * 24 * 3600
                    ),
                    "avg_latency_ms": stats.avg_latency,
                    "success_rate": stats.success_rate,
                    "expert_rate": stats.expert_rate,
                    "cache_rate": stats.cache_rate,
                    "model_size": cap.model_size,
                    "quantization": cap.quantization,
                    "compression_ratio": cap.compression_ratio,
                    "last_used": cap.last_used
                }

                # 生成建议
                recommendation = self._generate_domain_recommendation(domain, cap, stats)
                if recommendation:
                    plan["recommendations"].append(recommendation)

                plan["domain_status"][domain] = status

            # 能力分布汇总
            for level in CapabilityLevel:
                domains = [
                    d for d, c in self._domains.items()
                    if c.level == level and c.request_count > 0
                ]
                plan["capability_summary"][level.value] = {
                    "count": len(domains),
                    "domains": domains
                }

            return plan

    def _generate_domain_recommendation(
        self,
        domain: str,
        cap: DomainCapability,
        stats: DomainStats
    ) -> Optional[Dict[str, Any]]:
        """为单个领域生成建议"""
        recommendation = None

        # 检查是否需要升级
        recent = sum(
            1 for ts in stats.timestamps
            if time.time() - ts < 7 * 24 * 3600
        )

        if recent > 50 and cap.level == CapabilityLevel.COMPRESSED:
            recommendation = {
                "domain": domain,
                "action": "upgrade",
                "from": cap.level.value,
                "to": "standard",
                "reason": f"高频使用 ({recent}/周)，建议提升能力"
            }
        elif recent > 200 and cap.level != CapabilityLevel.FULL:
            recommendation = {
                "domain": domain,
                "action": "upgrade",
                "from": cap.level.value,
                "to": "full",
                "reason": f"超高频使用 ({recent}/周)，建议完整能力"
            }

        # 检查是否需要降级
        elif recent < 5 and cap.level != CapabilityLevel.OFFLOADED and cap.request_count > 20:
            recommendation = {
                "domain": domain,
                "action": "downgrade",
                "from": cap.level.value,
                "to": "compressed",
                "reason": f"使用频率低 ({recent}/周)，建议压缩节省资源"
            }

        # 检查低质量
        if stats.success_rate < 0.7 and cap.level != CapabilityLevel.FULL:
            if recommendation:
                recommendation["reason"] += f"，成功率低 ({stats.success_rate:.0%})"
            else:
                recommendation = {
                    "domain": domain,
                    "action": "investigate",
                    "from": cap.level.value,
                    "to": cap.level.value,
                    "reason": f"成功率低 ({stats.success_rate:.0%})，建议检查"
                }

        return recommendation

    def apply_compression(self, plan: Dict[str, Any]):
        """应用压缩计划"""
        with self._lock:
            for rec in plan.get("recommendations", []):
                if rec["action"] in ["upgrade", "downgrade"]:
                    domain = rec["domain"]
                    if domain in self._domains:
                        new_level = CapabilityLevel(rec["to"])
                        old_level = self._domains[domain].level
                        self._domains[domain].level = new_level
                        logger.info(f"[Compressor] Applied: {domain} {old_level.value} -> {new_level.value}")

        self._save_config()

    def get_domain_level(self, domain: str) -> CapabilityLevel:
        """获取领域能力等级"""
        if domain in self._domains:
            return self._domains[domain].level
        return CapabilityLevel.OFFLOADED  # 默认卸载

    def suggest_model_for_domain(
        self,
        domain: str,
        available_models: List[str]
    ) -> Optional[str]:
        """
        为领域推荐合适的模型

        Args:
            domain: 领域名称
            available_models: 可用模型列表

        Returns:
            推荐的模型名
        """
        if domain not in self._domains:
            return available_models[0] if available_models else None

        cap = self._domains[domain]

        # 根据能力等级筛选
        if cap.level == CapabilityLevel.FULL:
            # 完整能力：优先选大模型
            for m in available_models:
                if "7b" in m or "8b" in m:
                    return m
        elif cap.level == CapabilityLevel.STANDARD:
            # 标准能力：选中等模型
            for m in available_models:
                if "3b" in m or "4b" in m:
                    return m
        elif cap.level == CapabilityLevel.COMPRESSED:
            # 压缩能力：选小模型
            for m in available_models:
                if "1b" in m or "2b" in m:
                    return m
        else:
            # 卸载：按需加载
            return None

        # 回退：返回最小的
        return available_models[-1] if available_models else None

    def get_high_frequency_domains(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """获取高频领域"""
        with self._lock:
            domains_with_count = [
                (d, c.request_count)
                for d, c in self._domains.items()
                if c.request_count > 0
            ]
            return sorted(domains_with_count, key=lambda x: x[1], reverse=True)[:top_n]

    def get_low_frequency_domains(self, threshold: int = 5) -> List[str]:
        """获取低频领域（可压缩）"""
        with self._lock:
            return [
                d for d, c in self._domains.items()
                if c.request_count > 0 and c.request_count < threshold
            ]

    def get_inactive_domains(self, days: int = 30) -> List[str]:
        """获取不活跃领域（可卸载）"""
        with self._lock:
            threshold = time.time() - days * 24 * 3600
            return [
                d for d, c in self._domains.items()
                if c.last_used < threshold and c.request_count > 0
            ]

    def _save_config(self):
        """保存配置"""
        try:
            config = {
                "domains": {
                    domain: {
                        "level": cap.level.value,
                        "priority": cap.priority,
                        "request_count": cap.request_count,
                        "last_used": cap.last_used
                    }
                    for domain, cap in self._domains.items()
                }
            }

            config_path = self._data_dir / "compression_config.json"
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.info(f"[Compressor] Save config failed: {e}")

    def _load_config(self):
        """加载配置"""
        try:
            config_path = self._data_dir / "compression_config.json"
            if not config_path.exists():
                return

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            for domain, data in config.get("domains", {}).items():
                if domain in self._domains:
                    self._domains[domain].level = CapabilityLevel(data["level"])
                    self._domains[domain].priority = data.get("priority", 5)
                    self._domains[domain].request_count = data.get("request_count", 0)
                    self._domains[domain].last_used = data.get("last_used", 0)

        except Exception as e:
            logger.info(f"[Compressor] Load config failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            active_domains = [d for d, c in self._domains.items() if c.request_count > 0]

            return {
                "total_requests": self._total_requests,
                "total_domains": len(self._domains),
                "active_domains": len(active_domains),
                "uptime_seconds": time.time() - self._start_time,
                "capability_distribution": {
                    level.value: len([
                        d for d, c in self._domains.items()
                        if c.level == level
                    ])
                    for level in CapabilityLevel
                },
                "top_domains": self.get_high_frequency_domains(5),
                "low_freq_count": len(self.get_low_frequency_domains()),
                "inactive_count": len(self.get_inactive_domains(30))
            }


# ── 便捷函数 ──────────────────────────────────────────────────────────────

_compressor: Optional[AdaptiveModelCompressor] = None


def get_model_compressor() -> AdaptiveModelCompressor:
    """获取全局模型压缩器"""
    global _compressor
    if _compressor is None:
        _compressor = AdaptiveModelCompressor()
    return _compressor
