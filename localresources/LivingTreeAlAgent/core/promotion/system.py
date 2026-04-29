# system.py — 统一调度器

import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from .models import (
    AdTemplate, AdTemplateType, AttributionSource,
    PromotionResult, AdCampaign, LandingPageConfig,
)

from .template_engine import TemplateEngine, get_template_engine
from .attribution import AttributionSystem, get_attribution_system
from .landing_page import LandingPageGenerator, get_landing_page_generator


class PromotionSystem:
    """
    软广推广系统 — 统一调度器

    整合四大引擎：
    1. TemplateEngine — 差异化模板库
    2. AttributionSystem — 归因追踪
    3. LandingPageGenerator — 静态页生成
    4. CampaignManager — 活动管理
    """

    def __init__(
        self,
        templates: List[AdTemplate] = None,
        config: LandingPageConfig = None,
        data_dir: Path = None,
    ):
        """
        初始化推广系统

        Args:
            templates: 自定义模板列表
            config: 落地页配置
            data_dir: 数据存储目录
        """
        # 子系统
        self._engine = TemplateEngine(templates)
        self._attribution = get_attribution_system()
        self._generator = LandingPageGenerator(config)

        # 数据目录
        self._data_dir = data_dir or Path.home() / ".hermes-desktop" / "promotion"
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # 活动存储
        self._campaigns_file = self._data_dir / "campaigns.json"
        self._campaigns: Dict[str, AdCampaign] = {}
        self._load_campaigns()

    def _load_campaigns(self):
        """加载活动数据"""
        if self._campaigns_file.exists():
            try:
                import json
                with open(self._campaigns_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        self._campaigns[item["campaign_id"]] = AdCampaign(
                            campaign_id=item["campaign_id"],
                            name=item["name"],
                            description=item.get("description", ""),
                            templates=[AdTemplateType(t) for t in item.get("templates", [])],
                            target_sources=[AttributionSource(s) for s in item.get("target_sources", [])],
                            is_active=item.get("is_active", True),
                            stats=item.get("stats", {}),
                        )
            except Exception:
                pass

    def _save_campaigns(self):
        """保存活动数据"""
        import json
        data = [c.to_dict() for c in self._campaigns.values()]
        with open(self._campaigns_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def generate_ad(
        self,
        content: str,
        title: str = "",
        tags: List[str] = None,
        source: AttributionSource = AttributionSource.MANUAL,
        source_identity: str = "manual_user",
        campaign_id: Optional[str] = None,
        use_short_url: bool = True,
    ) -> PromotionResult:
        """
        生成软广（含归因链接）

        完整流程：
        1. 匹配最佳模板
        2. 生成软广文本
        3. 创建归因记录
        4. 返回结果
        """
        if tags is None:
            tags = []

        # 1. 模板匹配
        ad_text, match = self._engine.generate_ad(
            content=content,
            title=title,
            tags=tags,
            link="",
            summary=content[:200] if len(content) > 200 else content,
        )

        # 2. 内容哈希
        content_hash = self._engine.content_hash(content, title)

        # 3. 生成归因记录
        landing_url = self._generator.get_page_url()
        attribution = self._attribution.generate_short_url(
            source=source,
            source_identity=source_identity,
            campaign_id=campaign_id,
            content_hash=content_hash,
            full_url=landing_url,
        )

        # 4. 填充链接
        short_url = attribution.short_url if use_short_url else attribution.full_url
        ad_text = ad_text.replace("{link}", short_url)
        if short_url not in ad_text:
            ad_text = f"{ad_text}\n\n链接：{short_url}"

        # 5. 更新活动统计
        if campaign_id and campaign_id in self._campaigns:
            self._campaigns[campaign_id].stats["impressions"] += 1
            self._save_campaigns()

        return PromotionResult(
            ad_text=ad_text,
            matched_template=match,
            attribution=attribution,
            short_url=short_url,
            full_url=attribution.full_url,
            campaign_id=campaign_id,
            generated_at=datetime.now(),
        )

    def pick_ad_template(self, tags: List[str]) -> AdTemplate:
        """根据标签选择模板（简化API）"""
        return self._engine.pick_ad_template(tags)

    def generate_ad_preview(
        self,
        content: str,
        title: str = "",
        tags: List[str] = None,
        link: str = "https://lvtree.ai/v1?from=test",
    ) -> str:
        """生成软广预览（不含归因）"""
        ad_text, _ = self._engine.generate_ad(
            content=content,
            title=title,
            tags=tags,
            link=link,
        )
        return ad_text

    def generate_multiple_variants(
        self,
        content: str,
        title: str = "",
        tags: List[str] = None,
        count: int = 3,
    ) -> List[PromotionResult]:
        """生成多个软广变体"""
        if tags is None:
            tags = []

        results = []
        for i in range(count):
            result = self.generate_ad(
                content=content,
                title=title,
                tags=tags,
                source_identity=f"ab_test_{i}",
            )
            results.append(result)

        return results

    def generate_landing_page(
        self,
        attribution_id: Optional[str] = None,
        output_file: str = None,
    ) -> str:
        """生成静态落地页"""
        return self._generator.generate_and_save(attribution_id, output_file)

    def get_stats(self) -> Dict[str, Any]:
        """获取系统统计"""
        attribution_stats = self._attribution.get_all_stats()

        campaign_stats = {}
        for cid, campaign in self._campaigns.items():
            campaign_stats[cid] = {
                "name": campaign.name,
                "stats": campaign.stats,
                "is_active": campaign.is_active,
            }

        template_stats = self._engine.get_template_stats()

        return {
            "attribution": attribution_stats,
            "campaigns": campaign_stats,
            "templates": template_stats,
        }

    def is_enabled(self) -> bool:
        """检查系统是否启用"""
        return True

    def get_template_engine(self) -> TemplateEngine:
        """获取模板引擎"""
        return self._engine

    def get_attribution_system(self) -> AttributionSystem:
        """获取归因系统"""
        return self._attribution

    def get_landing_page_generator(self) -> LandingPageGenerator:
        """获取落地页生成器"""
        return self._generator


# 全局单例
_system_instance: Optional[PromotionSystem] = None


def get_promotion_system() -> PromotionSystem:
    """获取推广系统全局实例"""
    global _system_instance
    if _system_instance is None:
        _system_instance = PromotionSystem()
    return _system_instance
