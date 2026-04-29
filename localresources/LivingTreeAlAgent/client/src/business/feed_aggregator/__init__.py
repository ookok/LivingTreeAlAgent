# Living Tree AI — 聚合推荐系统
# Feed Aggregator with Visual Enhancement

"""
视觉增强版信息聚合推荐系统

核心理念：一眼入心，越用越懂你

架构：
1. 媒体增强抓取层 (media_fetcher.py)
   - 优先提取首图/视频封面
   - 缩略图懒加载 (<100KB)

2. 自适应卡片 UI (feed_card.py)
   - 圆角 12px + 轻柔阴影
   - 悬停微放大 0.98s 过渡
   - 媒体区 120px 占位

3. 兴趣驯化引擎 (interest_engine.py)
   - 正向: 点击/停留 → 权重↑
   - 负向: 右击不感兴趣 → 权重↓30%

4. 安全守门员 (safety_filter.py)
   - 关键词粗筛 → Presidio → 云兜底
"""

from .system import FeedAggregatorSystem, get_feed_system

__all__ = [
    "FeedAggregatorSystem",
    "get_feed_system",
]