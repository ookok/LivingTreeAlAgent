"""
排序引擎
负责多源内容的智能混排
采用漏斗模型：初排 -> 精排 -> 去重
"""

import time
from dataclasses import dataclass
from typing import Optional
from enum import Enum

from .user_profile import UserProfile
from .recall import RawItem


class ContentType(Enum):
    """内容类型"""
    NEWS = "news"
    VIDEO = "video"
    PRODUCT = "product"


@dataclass
class RankedItem:
    """
    排序后的内容项
    """
    item_id: str
    content_type: ContentType
    title: str
    description: str
    url: str
    image_url: str
    source: str
    tags: list[str]
    score: float
    publish_time: float
    hot_score: float
    
    # 原始数据
    raw_item: RawItem = None
    
    @property
    def time_ago(self) -> str:
        """获取时间描述"""
        seconds = time.time() - self.publish_time
        if seconds < 3600:
            return f"{int(seconds / 60)}分钟前"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}小时前"
        else:
            return f"{int(seconds / 86400)}天前"


class RankingEngine:
    """
    排序引擎
    实现多维度打分和智能混排
    """
    
    def __init__(self):
        # 打分权重配置
        self.weights = {
            "interest_match": 0.4,    # 兴趣匹配度
            "hot_score": 0.3,          # 热度
            "time_decay": 0.2,        # 时间衰减
            "freshness": 0.1,         # 新鲜度
        }
    
    def rank(
        self,
        items: list[RawItem],
        user_profile: UserProfile,
        top_k: int = 10
    ) -> list[RankedItem]:
        """
        排序主函数
        
        Args:
            items: 原始内容列表
            user_profile: 用户画像
            top_k: 返回数量
        
        Returns:
            排序后的内容列表
        """
        if not items:
            return []
        
        # 1. 类型识别
        typed_items = self._classify_items(items)
        
        # 2. 打分
        scored_items = []
        for content_type, raw_items in typed_items.items():
            for item in raw_items:
                score = self._calculate_score(item, user_profile, content_type)
                ranked = RankedItem(
                    item_id=item.item_id,
                    content_type=content_type,
                    title=item.title,
                    description=item.description,
                    url=item.url,
                    image_url=item.image_url,
                    source=item.source,
                    tags=item.tags,
                    score=score,
                    publish_time=item.publish_time,
                    hot_score=item.hot_score,
                    raw_item=item
                )
                scored_items.append(ranked)
        
        # 3. 去重
        unique_items = self._deduplicate(scored_items)
        
        # 4. 排序
        sorted_items = sorted(unique_items, key=lambda x: x.score, reverse=True)
        
        # 5. 混排（按类型均匀分布）
        mixed_items = self._mix_by_type(sorted_items, top_k)
        
        return mixed_items
    
    def _classify_items(self, items: list[RawItem]) -> dict[ContentType, list[RawItem]]:
        """分类内容"""
        result = {
            ContentType.NEWS: [],
            ContentType.VIDEO: [],
            ContentType.PRODUCT: [],
        }
        
        for item in items:
            if "video" in item.source.lower() or "bilibili" in item.source.lower():
                result[ContentType.VIDEO].append(item)
            elif "product" in item.source.lower() or "jd" in item.source.lower() or "taobao" in item.source.lower():
                result[ContentType.PRODUCT].append(item)
            else:
                result[ContentType.NEWS].append(item)
        
        return result
    
    def _calculate_score(
        self,
        item: RawItem,
        profile: UserProfile,
        content_type: ContentType
    ) -> float:
        """
        计算综合得分
        
        分数 = 兴趣匹配 * 0.4 + 热度 * 0.3 + 时间衰减 * 0.2 + 新鲜度 * 0.1
        """
        # 1. 兴趣匹配度
        interest_score = self._calc_interest_score(item, profile)
        
        # 2. 热度分
        hot_score = min(1.0, item.hot_score)
        
        # 3. 时间衰减
        time_score = self._calc_time_decay(item.publish_time)
        
        # 4. 新鲜度
        freshness_score = 1.0 if (time.time() - item.publish_time) < 3600 else 0.5
        
        # 加权求和
        total_score = (
            interest_score * self.weights["interest_match"] +
            hot_score * self.weights["hot_score"] +
            time_score * self.weights["time_decay"] +
            freshness_score * self.weights["freshness"]
        )
        
        return total_score
    
    def _calc_interest_score(self, item: RawItem, profile: UserProfile) -> float:
        """计算兴趣匹配度"""
        if profile.is_cold_start or not profile.interests:
            return 0.5  # 冷启动时给中等分
        
        # 检查标签匹配
        top_interests = set(profile.get_top_interests(5))
        item_tags = set(item.tags)
        
        overlap = top_interests & item_tags
        if overlap:
            return 0.8 + 0.2 * (len(overlap) / len(top_interests))
        
        return 0.3
    
    def _calc_time_decay(self, publish_time: float) -> float:
        """
        计算时间衰减
        使用指数衰减，24小时衰减到50%
        """
        age_hours = (time.time() - publish_time) / 3600
        
        if age_hours < 1:
            return 1.0
        elif age_hours < 24:
            return 1.0 - 0.5 * (age_hours / 24)
        else:
            return 0.5 * (0.9 ** (age_hours - 24) / 24)
    
    def _deduplicate(self, items: list[RankedItem]) -> list[RankedItem]:
        """去重（基于标题相似度）"""
        seen = set()
        unique = []
        
        for item in items:
            # 使用标题前50字符作为去重键
            key = item.title[:50].lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        
        return unique
    
    def _mix_by_type(self, items: list[RankedItem], top_k: int) -> list[RankedItem]:
        """
        按类型混排
        策略：按比例穿插不同类型
        """
        if len(items) <= top_k:
            return items
        
        # 分桶
        buckets = {
            ContentType.NEWS: [],
            ContentType.VIDEO: [],
            ContentType.PRODUCT: [],
        }
        
        for item in items:
            buckets[item.content_type].append(item)
        
        # 混排比例：新闻60%，视频25%，商品15%
        result = []
        type_limits = {
            ContentType.NEWS: int(top_k * 0.6),
            ContentType.VIDEO: int(top_k * 0.25),
            ContentType.PRODUCT: int(top_k * 0.15),
        }
        
        # 轮询填充
        round_idx = 0
        while len(result) < top_k:
            added = False
            for ctype, limit in type_limits.items():
                if len(result) >= top_k:
                    break
                
                # 计算该类型的起始索引
                start_idx = round_idx % len(buckets[ctype]) if buckets[ctype] else 0
                if start_idx < len(buckets[ctype]):
                    item = buckets[ctype][start_idx]
                    if item not in result:
                        result.append(item)
                        added = True
            
            if not added:
                break
            round_idx += 1
        
        return result


# 全局实例
_ranking_engine: Optional[RankingEngine] = None


def get_ranking_engine() -> RankingEngine:
    """获取全局排序引擎"""
    global _ranking_engine
    if _ranking_engine is None:
        _ranking_engine = RankingEngine()
    return _ranking_engine
