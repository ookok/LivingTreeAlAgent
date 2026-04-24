# interest_engine.py — 兴趣驯化引擎
# 正向点击/停留 → 权重↑ | 负向右击"不感兴趣" → 权重↓30%

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any

from .models import FeedItem, InterestProfile, FeedConfig
from core.logger import get_logger
logger = get_logger('feed_aggregator.interest_engine')



class InterestEngine:
    """
    兴趣驯化引擎

    双向反馈机制：
    - 正向: 点击/停留/收藏 → 标签权重↑
    - 负向: 右击"不感兴趣" → 标签权重↓30%

    存储: MemPalace 存 user_interests
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path.home() / ".hermes-desktop" / "feed_aggregator"
        self.profile_path = self.data_dir / "user_interests.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.config = FeedConfig()
        self.profile = self._load_profile()

        # 行为记录（用于统计分析）
        self.behavior_history: List[Dict] = []
        self.max_history = 1000

    # ============================================================
    # 主 API
    # ============================================================

    def calculate_score(self, item: FeedItem) -> float:
        """
        计算内容兴趣分数

        综合因素：
        1. 标签匹配度
        2. 来源偏好
        3. 类型偏好
        4. 时间衰减
        5. 互动热度
        """
        score = 0.5  # 基础分

        # 标签匹配 (40%)
        tag_score = self._calculate_tag_score(item)
        score += tag_score * 0.4

        # 来源偏好 (20%)
        source_score = self._calculate_source_score(item)
        score += source_score * 0.2

        # 类型偏好 (15%)
        type_score = self._calculate_type_score(item)
        score += type_score * 0.15

        # 时间衰减 (15%)
        time_score = self._calculate_time_score(item)
        score += time_score * 0.15

        # 互动热度 (10%)
        engagement_score = self._calculate_engagement(item)
        score += engagement_score * 0.1

        item.interest_score = max(0.0, min(1.0, score))
        return item.interest_score

    def rank_items(self, items: List[FeedItem]) -> List[FeedItem]:
        """对内容列表排序"""
        for item in items:
            self.calculate_score(item)

        return sorted(items, key=lambda x: (
            x.interest_score,           # 兴趣分
            x.published_at or datetime.min,  # 时间
        ), reverse=True)

    # ============================================================
    # 反馈处理
    # ============================================================

    def record_click(self, item: FeedItem, stay_seconds: float = 0):
        """
        记录点击行为

        Args:
            item: 被点击的内容
            stay_seconds: 停留秒数
        """
        # 提升标签权重
        for tag in item.tags:
            self.profile.boost_tag(tag, amount=0.1)

        # 提升来源权重
        self.profile.boost_source(item.source.value, amount=0.05)

        # 提升类型权重
        self.profile.type_weights[item.feed_type.value] = \
            self.profile.type_weights.get(item.feed_type.value, 0.5) + 0.05

        # 统计
        self.profile.total_clicks += 1

        # 记录行为
        self._record_behavior("click", item, {"stay_seconds": stay_seconds})

        self._save_profile()

    def record_hide(self, item: FeedItem, reason: str = "not_interested"):
        """
        记录负向反馈

        右击"不感兴趣"时调用

        效果：
        1. 标签权重下降 30% (×0.7)
        2. 来源权重下降
        3. 卡片渐隐移除
        """
        # 降低标签权重 (衰减 30%)
        decay = self.config.interest_decay_factor  # 0.7
        for tag in item.tags:
            self.profile.decay_tag(tag, amount=1.0 - decay)

        # 降低来源权重
        current_source = self.profile.source_weights.get(item.source.value, 0.5)
        self.profile.source_weights[item.source.value] = current_source * decay

        # 降低类型权重
        current_type = self.profile.type_weights.get(item.feed_type.value, 0.5)
        self.profile.type_weights[item.feed_type.value] = current_type * decay

        # 统计
        self.profile.total_hides += 1

        # 记录行为
        self._record_behavior("hide", item, {"reason": reason})

        self._save_profile()

    def record_bookmark(self, item: FeedItem):
        """记录收藏"""
        for tag in item.tags:
            self.profile.boost_tag(tag, amount=0.2)  # 收藏权重更高

        self._record_behavior("bookmark", item, {})

        self._save_profile()

    def record_view(self, item: FeedItem, duration_seconds: float = 0):
        """记录浏览（曝光）"""
        self.profile.total_views += 1

        # 长时间浏览算半个点击
        if duration_seconds > 30:
            self.record_click(item, stay_seconds=duration_seconds)

        self._record_behavior("view", item, {"duration": duration_seconds})

    # ============================================================
    # 分数计算辅助
    # ============================================================

    def _calculate_tag_score(self, item: FeedItem) -> float:
        """计算标签匹配分"""
        if not item.tags:
            return 0.5

        total = 0.0
        for tag in item.tags:
            total += self.profile.get_tag_weight(tag)

        return total / len(item.tags)

    def _calculate_source_score(self, item: FeedItem) -> float:
        """计算来源偏好分"""
        return self.profile.source_weights.get(item.source.value, 0.5)

    def _calculate_type_score(self, item: FeedItem) -> float:
        """计算类型偏好分"""
        return self.profile.type_weights.get(item.feed_type.value, 0.5)

    def _calculate_time_score(self, item: FeedItem) -> float:
        """计算时间衰减分"""
        if not item.published_at:
            return 0.5

        days_old = (datetime.now() - item.published_at).days

        if days_old < 1:
            return 1.0
        elif days_old < 7:
            return 0.8
        elif days_old < 30:
            return 0.5
        else:
            return 0.2

    def _calculate_engagement(self, item: FeedItem) -> float:
        """计算互动热度分"""
        # 归一化 (假设 10000 是高热度)
        likes_norm = min(1.0, item.likes / 10000)
        comments_norm = min(1.0, item.comments / 1000)

        return (likes_norm * 0.7 + comments_norm * 0.3)

    # ============================================================
    # 行为记录
    # ============================================================

    def _record_behavior(self, action: str, item: FeedItem, extra: Dict):
        """记录行为到历史"""
        self.behavior_history.append({
            "action": action,
            "item_id": item.id,
            "tags": item.tags,
            "source": item.source.value,
            "timestamp": datetime.now().isoformat(),
            **extra,
        })

        # 限制历史长度
        if len(self.behavior_history) > self.max_history:
            self.behavior_history = self.behavior_history[-self.max_history:]

    # ============================================================
    # 画像持久化
    # ============================================================

    def _load_profile(self) -> InterestProfile:
        """加载用户画像"""
        if not self.profile_path.exists():
            return InterestProfile()

        try:
            with open(self.profile_path, encoding="utf-8") as f:
                data = json.load(f)

            profile = InterestProfile(
                tag_weights=data.get("tag_weights", {}),
                source_weights=data.get("source_weights", {}),
                type_weights=data.get("type_weights", {}),
                total_clicks=data.get("total_clicks", 0),
                total_views=data.get("total_views", 0),
                total_hides=data.get("total_hides", 0),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
            )
            return profile
        except Exception as e:
            logger.info(f"[InterestEngine] Load profile failed: {e}")
            return InterestProfile()

    def _save_profile(self):
        """保存用户画像"""
        data = {
            "tag_weights": self.profile.tag_weights,
            "source_weights": self.profile.source_weights,
            "type_weights": self.profile.type_weights,
            "total_clicks": self.profile.total_clicks,
            "total_views": self.profile.total_views,
            "total_hides": self.profile.total_hides,
            "updated_at": self.profile.updated_at.isoformat(),
        }

        try:
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.info(f"[InterestEngine] Save profile failed: {e}")

    # ============================================================
    # 统计
    # ============================================================

    def get_top_tags(self, limit: int = 10) -> List[tuple]:
        """获取最高权重标签"""
        sorted_tags = sorted(
            self.profile.tag_weights.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_tags[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            **self.profile.get_stats(),
            "top_tags": self.get_top_tags(5),
            "behavior_history_size": len(self.behavior_history),
        }


# 全局单例
_interest_engine: Optional[InterestEngine] = None


def get_interest_engine() -> InterestEngine:
    global _interest_engine
    if _interest_engine is None:
        _interest_engine = InterestEngine()
    return _interest_engine
