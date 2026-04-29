# decision_engine.py — 开源库择优决策引擎

import json
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from dataclasses import asdict
from datetime import datetime

from .scanner_models import (
    ScanSource, CompareResult, CompareDimension,
    ReplacementDecision, CandidateLibrary, ScanTask,
    MirrorSource, MirrorConfig,
)


logger = logging.getLogger(__name__)


# ============ 决策规则配置 ============

DEFAULT_DECISION_RULES = {
    # 维度权重 (可调整)
    "dimension_weights": {
        CompareDimension.FEATURE_COVERAGE: 0.25,
        CompareDimension.RFC_COMPATIBILITY: 0.15,
        CompareDimension.MEMORY_FOOTPRINT: 0.10,
        CompareDimension.LICENSE_COMPLIANCE: 0.20,
        CompareDimension.MAINTENANCE_STATUS: 0.15,
        CompareDimension.COMMUNITY活跃度: 0.15,
        CompareDimension.PERFORMANCE: 0.0,  # 暂不使用
    },
    # 决策阈值
    "thresholds": {
        "min_stars_for_adopt": 500,       # 直接采用的最低stars
        "min_stars_for_wrap": 100,        # 封装采用的最低stars
        "max_memory_penalty": 0.3,        # 最大内存惩罚
        "min_confidence": 0.6,            # 最小置信度
    },
    # 必选协议
    "allowed_licenses": ["MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "ISC"],
    # 黑名单关键词
    "blacklist_keywords": ["enterprise", "commercial", "proprietary"],
}


# ============ 决策引擎 ============

class DecisionEngine:
    """
    择优决策引擎

    根据多维度比对结果，做出是否采用开源库的决策
    """

    def __init__(
        self,
        rules: Dict[str, Any] = None,
        custom_evaluate_fn: Callable = None,
    ):
        """
        初始化决策引擎

        Args:
            rules: 决策规则配置
            custom_evaluate_fn: 自定义评估函数 (可选)
        """
        self._rules = rules or DEFAULT_DECISION_RULES.copy()
        self._custom_evaluate_fn = custom_evaluate_fn
        self._decision_history: List[Dict[str, Any]] = []

    def evaluate(
        self,
        candidate: CandidateLibrary,
        module_name: str,
        custom_code_size: int = 0,
    ) -> Dict[str, Any]:
        """
        评估候选库

        Args:
            candidate: 候选库
            module_name: 模块名
            custom_code_size: 自研代码行数

        Returns:
            Dict: 评估结果
        """
        lib = candidate.library
        compares = candidate.compare_results

        # 1. 基础评分
        dimension_scores = self._calculate_dimension_scores(compares)

        # 2. 综合评分
        overall_oss_score = sum(
            dimension_scores[d.value] * self._rules["dimension_weights"].get(d, 0)
            for d in dimension_scores.keys()
        )
        overall_custom_score = sum(
            (1 - dimension_scores[d.value]) * self._rules["dimension_weights"].get(d, 0)
            for d in dimension_scores.keys()
        )

        # 3. 应用规则修正
        adjusted_score = self._apply_rules(
            overall_oss_score,
            lib,
            custom_code_size,
        )

        # 4. 最终决策
        decision = self._make_decision(
            adjusted_score,
            lib,
            dimension_scores,
        )

        # 5. 构建评估结果
        result = {
            "candidate": candidate.to_dict(),
            "module_name": module_name,
            "dimension_scores": dimension_scores,
            "overall_oss_score": overall_oss_score,
            "overall_custom_score": overall_custom_score,
            "adjusted_score": adjusted_score,
            "decision": decision.value if isinstance(decision, ReplacementDecision) else decision,
            "confidence": candidate.confidence,
            "benefits": candidate.benefits,
            "risks": candidate.risks,
            "estimated_effort_hours": candidate.estimated_effort_hours,
            "recommendation": self._get_recommendation_text(decision, lib),
            "timestamp": int(time.time()),
        }

        # 记录历史
        self._decision_history.append(result)

        return result

    def _calculate_dimension_scores(self, compares: List[CompareResult]) -> Dict[str, float]:
        """计算各维度评分"""
        scores = {}
        for c in compares:
            dim = c.dimension.value if isinstance(c.dimension, CompareDimension) else c.dimension
            # 标准化到 0-1, 值越大表示开源库越优
            scores[dim] = c.oss_score
        return scores

    def _apply_rules(
        self,
        base_score: float,
        library_info,
        custom_code_size: int,
    ) -> float:
        """应用规则修正评分"""
        adjusted = base_score
        lib_name = library_info.name.lower()

        # 1. Stars修正
        if library_info.stars < self._rules["thresholds"]["min_stars_for_wrap"]:
            adjusted *= 0.7  # 低Stars惩罚
        elif library_info.stars > self._rules["thresholds"]["min_stars_for_adopt"]:
            adjusted *= 1.1  # 高Stars奖励 (上限1.0)

        # 2. 协议修正
        if library_info.license not in self._rules["allowed_licenses"]:
            adjusted *= 0.3  # 协议不兼容严厉惩罚
        elif library_info.license == "MIT":
            adjusted *= 1.05  # MIT略微奖励

        # 3. 黑名单关键词检查
        for keyword in self._rules["blacklist_keywords"]:
            if keyword in lib_name:
                adjusted *= 0.1  # 黑名单关键词严厉惩罚
                break

        # 4. 内存占用惩罚
        for c in library_info.compare_results:
            if c.dimension == CompareDimension.MEMORY_FOOTPRINT:
                if c.oss_score < 0.5:  # 内存占用大
                    penalty = self._rules["thresholds"]["max_memory_penalty"]
                    adjusted *= (1 - penalty)

        # 5. 自研代码量大，倾向于保留
        if custom_code_size > 5000:
            adjusted *= 0.8  # 大规模自研代码，保守决策
        elif custom_code_size > 10000:
            adjusted *= 0.6  # 超大规模，更加保守

        # 6. 自定义评估函数
        if self._custom_evaluate_fn:
            try:
                custom_score = self._custom_evaluate_fn(library_info, custom_code_size)
                if custom_score is not None:
                    adjusted = adjusted * 0.7 + custom_score * 0.3
            except Exception as e:
                logger.warning(f"Custom evaluate fn failed: {e}")

        return max(0.0, min(1.0, adjusted))

    def _make_decision(
        self,
        score: float,
        library_info,
        dimension_scores: Dict[str, float],
    ) -> ReplacementDecision:
        """根据评分做出决策"""
        thresholds = self._rules["thresholds"]

        # 1. 协议不兼容，直接拒绝
        if library_info.license not in self._rules["allowed_licenses"]:
            return ReplacementDecision.REJECT

        # 2. 黑名单关键词
        for keyword in self._rules["blacklist_keywords"]:
            if keyword in library_info.name.lower():
                return ReplacementDecision.REJECT

        # 3. 高分决策
        if score >= 0.75 and library_info.stars >= thresholds["min_stars_for_adopt"]:
            return ReplacementDecision.ADOPT
        elif score >= 0.6 and library_info.stars >= thresholds["min_stars_for_wrap"]:
            return ReplacementDecision.WRAP_AND_ADOPT
        elif score >= 0.5:
            return ReplacementDecision.WRAP_AND_ADOPT
        elif score >= 0.35:
            return ReplacementDecision.DEFER
        else:
            return ReplacementDecision.KEEP_CUSTOM

    def _get_recommendation_text(self, decision: ReplacementDecision, library_info) -> str:
        """获取决策建议文本"""
        if decision == ReplacementDecision.ADOPT:
            return f"推荐直接采用 {library_info.name}。Stars: {library_info.stars}，功能完善，维护活跃。"
        elif decision == ReplacementDecision.WRAP_AND_ADOPT:
            return f"建议封装后采用 {library_info.name}。通过适配器封装，保持接口不变，业务零改动。"
        elif decision == ReplacementDecision.KEEP_CUSTOM:
            return f"建议保留自研。{library_info.name} 未显著优于当前实现。"
        elif decision == ReplacementDecision.DEFER:
            return f"建议延后决策。需更多评估或等待 {library_info.name} 更成熟。"
        elif decision == ReplacementDecision.REJECT:
            return f"不建议采用 {library_info.name}。协议不兼容或存在风险。"
        else:
            return "无法给出建议，需人工评估。"

    def batch_evaluate(
        self,
        candidates: List[CandidateLibrary],
        module_name: str,
        custom_code_size: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        批量评估候选库

        Args:
            candidates: 候选库列表
            module_name: 模块名
            custom_code_size: 自研代码行数

        Returns:
            List[Dict]: 评估结果列表 (已排序)
        """
        results = []
        for candidate in candidates:
            result = self.evaluate(candidate, module_name, custom_code_size)
            results.append(result)

        # 按 adjusted_score 降序排序
        results.sort(key=lambda r: r["adjusted_score"], reverse=True)
        return results

    def get_best_candidate(
        self,
        candidates: List[CandidateLibrary],
        module_name: str,
        custom_code_size: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """
        获取最佳候选

        Returns:
            最佳候选的评估结果，或None
        """
        results = self.batch_evaluate(candidates, module_name, custom_code_size)
        for r in results:
            if r["decision"] in [ReplacementDecision.ADOPT.value, ReplacementDecision.WRAP_AND_ADOPT.value]:
                return r
        return results[0] if results else None

    def get_decision_history(self) -> List[Dict[str, Any]]:
        """获取决策历史"""
        return self._decision_history

    def clear_history(self):
        """清空决策历史"""
        self._decision_history.clear()

    def update_rules(self, key: str, value: Any):
        """更新规则"""
        if "." in key:
            # 支持嵌套 key 如 "thresholds.min_stars"
            parts = key.split(".")
            target = self._rules
            for p in parts[:-1]:
                target = target.setdefault(p, {})
            target[parts[-1]] = value
        else:
            self._rules[key] = value

    def export_rules(self) -> Dict[str, Any]:
        """导出当前规则"""
        return self._rules.copy()


# ============ 镜像源健康度管理器 ============

class MirrorHealthManager:
    """
    镜像源健康度管理器

    功能：
    1. 跟踪各镜像源健康状态
    2. 自动选择最佳镜像
    3. 故障时自动切换
    """

    def __init__(self, config_dir: Path = None):
        if config_dir is None:
            config_dir = Path.home() / ".hermes-desktop" / "upgrade_scanner"
        config_dir.mkdir(parents=True, exist_ok=True)
        self._config_file = config_dir / "mirror_config.json"
        self._configs: Dict[str, MirrorConfig] = {}
        self._load_config()

    def _load_config(self):
        """加载配置"""
        if self._config_file.exists():
            try:
                data = json.loads(self._config_file.read_text(encoding="utf-8"))
                for k, v in data.items():
                    self._configs[k] = MirrorConfig(**v)
            except Exception:
                self._init_default_config()

    def _init_default_config(self):
        """初始化默认配置"""
        self._configs = {
            "github": MirrorConfig(
                source=MirrorSource.GITHUB,
                base_url="https://github.com",
                priority=1,
                timeout_seconds=8.0,
            ),
            "gitee": MirrorConfig(
                source=MirrorSource.Gitee,
                base_url="https://gitee.com",
                priority=2,
                timeout_seconds=5.0,
            ),
            "aliyun": MirrorConfig(
                source=MirrorSource.ALIYUN,
                base_url="https://mirrors.aliyun.com",
                priority=3,
                timeout_seconds=5.0,
            ),
            "tinghua": MirrorConfig(
                source=MirrorSource.TINGHUA,
                base_url="https://mirrors.tuna.tsinghua.edu.cn",
                priority=4,
                timeout_seconds=5.0,
            ),
        }

    def _save_config(self):
        """保存配置"""
        try:
            data = {
                k: v.to_dict() for k, v in self._configs.items()
            }
            self._config_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Failed to save mirror config: {e}")

    def get_best_mirror(self, source_type: str = "github") -> Optional[MirrorConfig]:
        """
        获取最佳镜像

        Args:
            source_type: 源类型 (github/gitee/pypi)

        Returns:
            最佳镜像配置
        """
        candidates = []
        for key, config in self._configs.items():
            if not config.enabled:
                continue
            if source_type in key or key == source_type:
                health = self._calculate_health(config)
                candidates.append((health, config))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _calculate_health(self, config: MirrorConfig) -> float:
        """计算健康评分"""
        total = config.success_count + config.failure_count
        if total == 0:
            return 1.0  # 默认健康

        success_rate = config.success_count / total

        # 时间衰减
        time_factor = 1.0
        if config.last_check:
            age = time.time() - config.last_check
            if age > 3600:
                time_factor = 0.9
            elif age > 86400:
                time_factor = 0.7

        return success_rate * time_factor

    async def check_mirror_health(self, config: MirrorConfig) -> bool:
        """
        检查镜像健康状态

        Returns:
            是否健康
        """
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                start = time.time()
                async with session.get(
                    config.base_url,
                    timeout=aiohttp.ClientTimeout(total=config.timeout_seconds),
                ) as resp:
                    elapsed = time.time() - start
                    if resp.status == 200:
                        config.success_count += 1
                        config.health_score = min(1.0, elapsed / config.timeout_seconds)
                    else:
                        config.failure_count += 1
                    config.last_check = int(time.time())
                    self._save_config()
                    return resp.status < 500
        except Exception:
            config.failure_count += 1
            config.last_check = int(time.time())
            self._save_config()
            return False

    def record_success(self, mirror_key: str):
        """记录成功"""
        if mirror_key in self._configs:
            self._configs[mirror_key].success_count += 1
            self._save_config()

    def record_failure(self, mirror_key: str):
        """记录失败"""
        if mirror_key in self._configs:
            self._configs[mirror_key].failure_count += 1
            self._save_config()

    def get_all_mirrors(self) -> List[MirrorConfig]:
        """获取所有镜像配置"""
        return list(self._configs.values())

    def get_mirror_by_source(self, source: MirrorSource) -> Optional[MirrorConfig]:
        """根据源类型获取镜像"""
        for config in self._configs.values():
            if config.source == source:
                return config
        return None


# ============ 全局实例 ============

_decision_engine: Optional[DecisionEngine] = None
_mirror_manager: Optional[MirrorHealthManager] = None


def get_decision_engine() -> DecisionEngine:
    """获取决策引擎全局实例"""
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = DecisionEngine()
    return _decision_engine


def get_mirror_manager() -> MirrorHealthManager:
    """获取镜像管理器全局实例"""
    global _mirror_manager
    if _mirror_manager is None:
        _mirror_manager = MirrorHealthManager()
    return _mirror_manager
