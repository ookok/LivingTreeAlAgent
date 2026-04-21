"""
Anti-Spam - 反滥用与垃圾过滤系统
=================================

功能：
- 信誉评分
- 垃圾内容检测
- 速率限制
- 内容质量评估

Author: LivingTreeAI Community
"""

import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, List, Dict, Set
from enum import Enum
from collections import defaultdict


class SpamScore(Enum):
    """垃圾分数级别"""
    CLEAN = "clean"       # 干净
    SUSPICIOUS = "suspicious"  # 可疑
    LIKELY_SPAM = "likely_spam"  # 可能是垃圾
    DEFINITE_SPAM = "definite_spam"  # 确定垃圾


@dataclass
class ReputationSystem:
    """
    信誉系统

    追踪每个节点的信誉评分
    """

    def __init__(self):
        # 节点信誉 {node_id: score}
        self._reputations: Dict[str, float] = defaultdict(lambda: 1.0)

        # 信誉历史
        self._history: Dict[str, List[float]] = defaultdict(list)

        # 统计
        self._contributions: Dict[str, int] = defaultdict(int)
        self._spam_reports: Dict[str, int] = defaultdict(int)
        self._false_positives: Dict[str, int] = defaultdict(int)

    def get_reputation(self, node_id: str) -> float:
        """获取节点信誉（0-1）"""
        return max(0.0, min(1.0, self._reputations.get(node_id, 1.0)))

    def update_reputation(self, node_id: str, delta: float, reason: str = ""):
        """
        更新节点信誉

        Args:
            node_id: 节点ID
            delta: 变化量（正负）
            reason: 更新原因
        """
        old_rep = self.get_reputation(node_id)
        new_rep = max(0.0, min(1.0, old_rep + delta))
        self._reputations[node_id] = new_rep

        # 记录历史
        self._history[node_id].append(new_rep)
        if len(self._history[node_id]) > 100:
            self._history[node_id] = self._history[node_id][-100:]

    def record_contribution(self, node_id: str):
        """记录贡献（增加信誉）"""
        self._contributions[node_id] += 1
        # 每10次贡献增加一点信誉
        if self._contributions[node_id] % 10 == 0:
            self.update_reputation(node_id, 0.01, "contribution")

    def report_spam(self, node_id: str):
        """举报垃圾（降低信誉）"""
        self._spam_reports[node_id] += 1
        # 每次举报降低信誉
        penalty = 0.1 * (1 + self._spam_reports[node_id] * 0.1)
        self.update_reputation(node_id, -penalty, "spam_report")

    def report_false_positive(self, node_id: str):
        """误报（略微降低信誉，因为误报也说明判断不准）"""
        self._false_positives[node_id] += 1
        self.update_reputation(node_id, -0.02, "false_positive")

    def get_stats(self, node_id: str) -> dict:
        """获取节点统计"""
        return {
            "reputation": self.get_reputation(node_id),
            "contributions": self._contributions.get(node_id, 0),
            "spam_reports": self._spam_reports.get(node_id, 0),
            "false_positives": self._false_positives.get(node_id, 0),
        }


@dataclass
class RateLimiter:
    """
    速率限制器

    基于时间窗口的速率限制
    """

    def __init__(self):
        # 速率限制规则
        self.limits = {
            "publish_post": {"per_minute": 3, "per_hour": 20, "per_day": 100},
            "send_email": {"per_minute": 5, "per_hour": 50, "per_day": 200},
            "broadcast": {"per_minute": 10, "per_hour": 100, "per_day": 500},
            "search": {"per_minute": 30, "per_hour": 300, "per_day": 1000},
        }

        # 计数器 {node_id}: {action: [(timestamp, count)]}
        self.counters: Dict[str, Dict[str, List[tuple]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def _cleanup_old_entries(self, node_id: str, action: str):
        """清理过期记录"""
        now = time.time()
        cutoff_day = now - 86400  # 1天前
        cutoff_hour = now - 3600  # 1小时前
        cutoff_minute = now - 60  # 1分钟前

        entries = self.counters[node_id][action]
        self.counters[node_id][action] = [
            (ts, count) for ts, count in entries
            if ts > cutoff_day
        ]

    def check_rate_limit(self, node_id: str, action: str) -> bool:
        """
        检查速率限制

        Returns:
            True 表示允许，False 表示超限
        """
        if action not in self.limits:
            return True

        self._cleanup_old_entries(node_id, action)

        now = time.time()
        entries = self.counters[node_id][action]

        # 检查各时间窗口
        limits = self.limits[action]
        for window_name, limit in limits.items():
            if window_name == "per_minute":
                cutoff = now - 60
            elif window_name == "per_hour":
                cutoff = now - 3600
            elif window_name == "per_day":
                cutoff = now - 86400
            else:
                continue

            # 统计该窗口内的请求数
            count = sum(
                count for ts, count in entries
                if ts > cutoff
            )

            if count >= limit:
                return False

        return True

    def record_action(self, node_id: str, action: str):
        """记录动作"""
        now = time.time()
        self.counters[node_id][action].append((now, 1))

    def get_remaining(self, node_id: str, action: str) -> dict:
        """获取剩余配额"""
        self._cleanup_old_entries(node_id, action)

        now = time.time()
        entries = self.counters[node_id][action]
        result = {}

        limits = self.limits.get(action, {})
        for window_name, limit in limits.items():
            if window_name == "per_minute":
                cutoff = now - 60
            elif window_name == "per_hour":
                cutoff = now - 3600
            elif window_name == "per_day":
                cutoff = now - 86400
            else:
                continue

            count = sum(
                count for ts, c in entries
                if ts > cutoff
            )

            result[window_name] = max(0, limit - count)

        return result


class AntiSpamSystem:
    """
    反垃圾系统

    功能：
    1. 内容质量评估
    2. 垃圾检测
    3. 信誉追踪
    4. 速率限制
    """

    # 垃圾关键词（简化示例）
    SPAM_KEYWORDS = {
        "免费", "赚钱", "优惠", "打折", "促销",
        "点击此处", "立即购买", "限时", "特价",
        "casino", "viagra", "lottery", "winner",
    }

    def __init__(
        self,
        node_id: str,
        reputation_func: Optional[Callable[[str], float]] = None,
    ):
        self.node_id = node_id

        # 子系统
        self.reputation = ReputationSystem()
        self.rate_limiter = RateLimiter()

        # 信誉函数（外部提供）
        self._get_reputation = reputation_func or self.reputation.get_reputation

        # 配置
        self.config = {
            "spam_threshold": 0.3,  # 低于此值判定为垃圾
            "suspicious_threshold": 0.7,  # 低于此值需要审核
            "author_reputation_weight": 0.4,
            "content_quality_weight": 0.3,
            "feedback_weight": 0.3,
        }

    def evaluate_content(
        self,
        content: Any,
        recipient_feedback: Optional[float] = None
    ) -> float:
        """
        评估内容质量

        Returns:
            0-1 分数，越高越可能是正常内容
        """
        score = 1.0

        # 1. 作者信誉（权重40%）
        author_rep = self._get_reputation(content.author)
        score *= (self.config["author_reputation_weight"] * author_rep * 2 +
                  (1 - self.config["author_reputation_weight"]))

        # 2. 内容特征（权重30%）
        content_quality = self._evaluate_content_quality(content)
        score *= (self.config["content_quality_weight"] * content_quality * 2 +
                  (1 - self.config["content_quality_weight"]))

        # 3. 收件人反馈（权重30%）
        if recipient_feedback is not None:
            score *= (self.config["feedback_weight"] * recipient_feedback * 2 +
                      (1 - self.config["feedback_weight"]))

        return max(0.0, min(1.0, score))

    def _evaluate_content_quality(self, content: Any) -> float:
        """评估内容质量特征"""
        quality = 1.0

        # 检查垃圾关键词
        spam_count = 0
        text = (content.title or "") + " " + (content.body or "")
        for keyword in self.SPAM_KEYWORDS:
            if keyword in text:
                spam_count += 1

        if spam_count > 0:
            quality *= max(0.1, 1.0 - spam_count * 0.2)

        # 检查内容长度
        body_len = len(content.body) if content.body else 0
        if body_len < 10:
            quality *= 0.5  # 太短
        elif body_len > 10000:
            quality *= 0.8  # 太长可能灌水

        # 检查标题
        title_len = len(content.title) if content.title else 0
        if title_len < 3:
            quality *= 0.5
        elif title_len > 100:
            quality *= 0.9

        return max(0.0, min(1.0, quality))

    def filter_content(
        self,
        content: Any,
        recipient_feedback: Optional[float] = None
    ) -> tuple[bool, SpamScore]:
        """
        过滤内容

        Returns:
            (是否允许, 垃圾评分级别)
        """
        # 评估分数
        score = self.evaluate_content(content, recipient_feedback)

        if score < self.config["spam_threshold"]:
            return False, SpamScore.DEFINITE_SPAM
        elif score < self.config["suspicious_threshold"]:
            return True, SpamScore.SUSPICIOUS
        else:
            return True, SpamScore.CLEAN

    def throttle_content(self, content: Any) -> float:
        """
        对内容进行限流

        Returns:
            需要延迟的秒数
        """
        score = self.evaluate_content(content)

        if score < 0.3:
            return 10.0  # 延迟10秒
        elif score < 0.5:
            return 5.0
        elif score < 0.7:
            return 2.0
        else:
            return 0.0

    def get_spam_score(self, content: Any) -> SpamScore:
        """获取垃圾评分级别"""
        score = self.evaluate_content(content)

        if score < self.config["spam_threshold"]:
            return SpamScore.DEFINITE_SPAM
        elif score < self.config["suspicious_threshold"]:
            return SpamScore.SUSPICIOUS
        elif score < 0.85:
            return SpamScore.LIKELY_SPAM
        else:
            return SpamScore.CLEAN

    def record_positive_interaction(
        self,
        author: str,
        content_id: str
    ):
        """记录正向互动"""
        self.reputation.record_contribution(author)

    def record_negative_interaction(
        self,
        author: str,
        content_id: str
    ):
        """记录负向互动"""
        self.reputation.report_spam(author)

    def record_false_positive(
        self,
        author: str
    ):
        """记录误报"""
        self.reputation.report_false_positive(author)

    def check_rate_limit(self, node_id: str, action: str) -> bool:
        """检查速率限制"""
        return self.rate_limiter.check_rate_limit(node_id, action)

    def record_action(self, node_id: str, action: str):
        """记录动作"""
        self.rate_limiter.record_action(node_id, action)

    def get_rate_limit_status(self, node_id: str, action: str) -> dict:
        """获取速率限制状态"""
        return self.rate_limiter.get_remaining(node_id, action)

    def get_author_stats(self, author: str) -> dict:
        """获取作者统计"""
        return self.reputation.get_stats(author)

    def get_stats(self) -> dict:
        """获取系统统计"""
        return {
            "reputation_count": len(self.reputation._reputations),
            "rate_limited_actions": sum(
                len(actions)
                for actions in self.rate_limiter.counters.values()
            ),
        }


# 全局单例
_antispam_instance: Optional[AntiSpamSystem] = None


def get_anti_spam(node_id: str = "local") -> AntiSpamSystem:
    """获取反垃圾系统单例"""
    global _antispam_instance
    if _antispam_instance is None:
        _antispam_instance = AntiSpamSystem(node_id)
    return _antispam_instance