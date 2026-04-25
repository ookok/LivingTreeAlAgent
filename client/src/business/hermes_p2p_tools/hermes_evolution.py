"""
Hermes驱动的自适应引导进化系统
==============================

核心理念：将自适应引导从"静态规则"升级为"动态进化的智能体"

1. 记忆集成
   - 引导成功经验 → 沉淀到Hermes记忆
   - 失败教训 → 记录并避免重蹈
   - 用户偏好 → 个性化引导策略

2. 技能自进化
   - 成功的引导流程 → 自动生成为Skill模板
   - 优化引导步骤 → 缩短引导路径
   - 适应用户习惯 → 提供"最常用"优先

3. 意图理解升级
   - 模糊意图 → Hermes深度理解
   - 上下文感知 → 联想相关配置
   - 主动建议 → 预测用户需求

Author: Hermes Desktop AI Assistant
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class EvolutionEvent(Enum):
    """进化事件类型"""
    GUIDE_START = "guide_start"
    GUIDE_SUCCESS = "guide_success"
    GUIDE_FAIL = "guide_fail"
    GUIDE_SKIP = "guide_skip"
    USER_FEEDBACK = "user_feedback"
    CONFIG_COMPLETE = "config_complete"


@dataclass
class EvolutionRecord:
    """进化记录"""
    event: EvolutionEvent
    feature_id: str
    guide_id: str
    timestamp: str
    duration_seconds: float
    steps_completed: int
    total_steps: int
    user_profile: Dict[str, Any]
    outcome: str
    metadata: Dict = field(default_factory=dict)


class HermesGuideEvolution:
    """
    Hermes驱动的引导进化系统

    功能：
    1. 跟踪引导事件
    2. 分析引导效果
    3. 自动优化引导策略
    4. 生成个性化引导

    使用示例：
        evolution = HermesGuideEvolution()

        # 记录引导开始
        evolution.record_event(EvolutionEvent.GUIDE_START, "weather_api", guide_id="xxx")

        # 记录成功
        evolution.record_event(EvolutionEvent.GUIDE_SUCCESS, "weather_api", guide_id="xxx")

        # 获取优化后的引导
        optimized_guide = evolution.get_optimized_guide("weather_api", user_profile)
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".hermes" / "guide_evolution"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._records: List[EvolutionRecord] = []
        self._load_records()

        # 统计缓存
        self._stats_cache: Dict[str, Dict] = {}
        self._last_cache_time = 0
        self._cache_ttl = 300  # 5分钟

    # ── 事件记录 ──────────────────────────────────────────────────────

    def record_event(
        self,
        event: EvolutionEvent,
        feature_id: str,
        guide_id: str,
        duration_seconds: float = 0,
        steps_completed: int = 0,
        total_steps: int = 0,
        outcome: str = "",
        metadata: Optional[Dict] = None
    ):
        """
        记录引导事件

        Args:
            event: 事件类型
            feature_id: 功能ID
            guide_id: 引导ID
            duration_seconds: 耗时
            steps_completed: 完成步数
            total_steps: 总步数
            outcome: 结果描述
            metadata: 额外数据
        """
        from client.src.business.user_profile_detector import get_user_profile_detector

        try:
            profile_detector = get_user_profile_detector()
            user_profile = profile_detector.detect_profile().__dict__ if profile_detector else {}
        except:
            user_profile = {}

        record = EvolutionRecord(
            event=event,
            feature_id=feature_id,
            guide_id=guide_id,
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration_seconds,
            steps_completed=steps_completed,
            total_steps=total_steps,
            user_profile=user_profile,
            outcome=outcome,
            metadata=metadata or {}
        )

        self._records.append(record)
        self._save_records()

        # 触发进化分析
        if event in (EvolutionEvent.GUIDE_SUCCESS, EvolutionEvent.GUIDE_FAIL):
            self._analyze_and_evolve(feature_id)

        logger.info(f"记录引导事件: {event.value} - {feature_id}")

    def record_guide_success(
        self,
        feature_id: str,
        guide_id: str,
        duration: float,
        steps: int,
        total_steps: int,
        user_profile: Dict
    ):
        """快捷方法：记录引导成功"""
        self.record_event(
            event=EvolutionEvent.GUIDE_SUCCESS,
            feature_id=feature_id,
            guide_id=guide_id,
            duration_seconds=duration,
            steps_completed=steps,
            total_steps=total_steps,
            outcome="completed",
            metadata={"success": True}
        )

        # 保存成功经验到记忆
        self._save_success_to_memory(feature_id, guide_id, duration, user_profile)

    def record_guide_failure(
        self,
        feature_id: str,
        guide_id: str,
        error: str,
        failed_at_step: int
    ):
        """快捷方法：记录引导失败"""
        self.record_event(
            event=EvolutionEvent.GUIDE_FAIL,
            feature_id=feature_id,
            guide_id=guide_id,
            steps_completed=failed_at_step,
            outcome=error
        )

        # 保存失败教训到记忆
        self._save_failure_to_memory(feature_id, guide_id, error, failed_at_step)

    # ── 进化分析 ──────────────────────────────────────────────────────

    def _analyze_and_evolve(self, feature_id: str):
        """分析引导效果并触发进化"""
        stats = self.get_feature_stats(feature_id)

        if stats["success_count"] >= 3:
            # 成功3次以上，尝试优化
            self._optimize_guide(feature_id, stats)

    def _optimize_guide(self, feature_id: str, stats: Dict):
        """优化引导策略"""
        # 分析最常用的步骤顺序
        success_records = [
            r for r in self._records
            if r.feature_id == feature_id and r.event == EvolutionEvent.GUIDE_SUCCESS
        ]

        if len(success_records) < 3:
            return

        # 计算平均耗时
        avg_duration = sum(r.duration_seconds for r in success_records) / len(success_records)

        # 检查是否可以跳过某些步骤
        steps_completion_rates = {}
        for record in success_records:
            if record.metadata.get("completed_steps"):
                for step in record.metadata["completed_steps"]:
                    steps_completion_rates[step] = steps_completion_rates.get(step, 0) + 1

        # 生成优化建议
        optimization = {
            "feature_id": feature_id,
            "avg_duration": avg_duration,
            "success_rate": stats["success_rate"],
            "suggested_shortcuts": [
                step for step, rate in steps_completion_rates.items()
                if rate / len(success_records) >= 0.9  # 90%的人都完成了
            ],
            "timestamp": datetime.now().isoformat()
        }

        # 保存优化建议
        self._save_optimization(feature_id, optimization)

        logger.info(f"引导优化建议已生成: {feature_id}")

    # ── 记忆集成 ──────────────────────────────────────────────────────

    def _save_success_to_memory(
        self,
        feature_id: str,
        guide_id: str,
        duration: float,
        user_profile: Dict
    ):
        """保存成功经验到Hermes记忆"""
        try:
            from client.src.business.memory_manager import MemoryManager

            mm = MemoryManager()

            # 生成记忆文本
            memory_text = f"""
引导成功案例沉淀：
- 功能: {feature_id}
- 引导ID: {guide_id}
- 耗时: {duration:.1f}秒
- 用户类型: {user_profile.get('tech_level', 'unknown')}
- 关键成功因素: {self._extract_success_factors(guide_id)}

这是一个有效的引导流程，可以作为后续同类用户的参考模板。
"""

            mm.append_memory(memory_text)
            logger.info(f"成功经验已保存到记忆: {feature_id}")

        except Exception as e:
            logger.warning(f"保存成功记忆失败: {e}")

    def _save_failure_to_memory(
        self,
        feature_id: str,
        guide_id: str,
        error: str,
        failed_at_step: int
    ):
        """保存失败教训到Hermes记忆"""
        try:
            from client.src.business.memory_manager import MemoryManager

            mm = MemoryManager()

            memory_text = f"""
引导失败教训记录：
- 功能: {feature_id}
- 引导ID: {guide_id}
- 失败步骤: 第{failed_at_step}步
- 错误原因: {error}

后续引导应避免在第{failed_at_step}步使用相同方式。
"""

            mm.append_memory(memory_text)

        except Exception as e:
            logger.warning(f"保存失败记忆失败: {e}")

    def _extract_success_factors(self, guide_id: str) -> List[str]:
        """提取成功因素"""
        # 简化实现，实际应分析具体步骤
        return ["浏览器自动化", "剪贴板自动检测", "分步引导"]

    # ── 统计与分析 ────────────────────────────────────────────────────

    def get_feature_stats(self, feature_id: str) -> Dict:
        """获取功能引导统计"""
        # 检查缓存
        if feature_id in self._stats_cache:
            if time.time() - self._last_cache_time < self._cache_ttl:
                return self._stats_cache[feature_id]

        feature_records = [r for r in self._records if r.feature_id == feature_id]

        total = len(feature_records)
        success = sum(1 for r in feature_records if r.event == EvolutionEvent.GUIDE_SUCCESS)
        failed = sum(1 for r in feature_records if r.event == EvolutionEvent.GUIDE_FAIL)

        avg_duration = 0
        if success > 0:
            durations = [
                r.duration_seconds for r in feature_records
                if r.event == EvolutionEvent.GUIDE_SUCCESS
            ]
            avg_duration = sum(durations) / len(durations)

        stats = {
            "feature_id": feature_id,
            "total_count": total,
            "success_count": success,
            "failed_count": failed,
            "success_rate": success / total if total > 0 else 0,
            "avg_duration_seconds": avg_duration,
            "last_event": feature_records[-1].timestamp if feature_records else None
        }

        self._stats_cache[feature_id] = stats
        self._last_cache_time = time.time()

        return stats

    def get_optimized_guide(
        self,
        feature_id: str,
        user_profile: Optional[Dict] = None
    ) -> Dict:
        """
        获取优化后的引导策略

        Args:
            feature_id: 功能ID
            user_profile: 用户画像

        Returns:
            优化后的引导配置
        """
        # 加载优化建议
        optimization_path = self.storage_path / f"{feature_id}_optimization.json"
        if optimization_path.exists():
            with open(optimization_path, "r", encoding="utf-8") as f:
                optimization = json.load(f)
        else:
            optimization = {}

        # 结合用户画像调整
        if user_profile:
            tech_level = user_profile.get("tech_level", "intermediate")
            if tech_level == "beginner":
                # 新手需要更多步骤
                optimization["step_multiplier"] = 1.2
            elif tech_level == "advanced":
                # 高手可以跳过基础
                optimization["skip_basic_steps"] = True

        return optimization

    # ── 持久化 ───────────────────────────────────────────────────────

    def _load_records(self):
        """加载历史记录"""
        records_path = self.storage_path / "records.json"
        if records_path.exists():
            try:
                with open(records_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        self._records.append(EvolutionRecord(**item))
            except Exception as e:
                logger.warning(f"加载记录失败: {e}")

    def _save_records(self):
        """保存记录"""
        records_path = self.storage_path / "records.json"
        try:
            with open(records_path, "w", encoding="utf-8") as f:
                data = [r.__dict__ for r in self._records[-1000:]]  # 只保留最近1000条
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存记录失败: {e}")

    def _save_optimization(self, feature_id: str, optimization: Dict):
        """保存优化建议"""
        optimization_path = self.storage_path / f"{feature_id}_optimization.json"
        try:
            with open(optimization_path, "w", encoding="utf-8") as f:
                json.dump(optimization, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存优化建议失败: {e}")


# ── 全局单例 ──────────────────────────────────────────────────────────────

_evolution_instance: Optional[HermesGuideEvolution] = None


def get_hermes_guide_evolution() -> HermesGuideEvolution:
    """获取进化系统单例"""
    global _evolution_instance

    if _evolution_instance is None:
        _evolution_instance = HermesGuideEvolution()

    return _evolution_instance