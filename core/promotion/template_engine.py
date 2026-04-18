# template_engine.py — 差异化模板库与智能匹配

import re
import random
import hashlib
from typing import List, Optional, Dict, Any, Tuple

from .models import (
    AdTemplate, AdTemplateType, TemplateMatch,
    TemplateMatchStrategy, DEFAULT_AD_TEMPLATES,
)


class TemplateEngine:
    """
    软广模板引擎

    功能：
    1. 四大独家卖点模板库
    2. 关键词智能匹配
    3. 软广文本生成
    4. A/B测试支持
    """

    def __init__(
        self,
        templates: List[AdTemplate] = None,
        default_fallback: bool = True,
        random_seed: Optional[int] = None,
    ):
        """
        初始化模板引擎

        Args:
            templates: 自定义模板列表，None则使用默认四大模板
            default_fallback: 是否启用默认兜底模板
            random_seed: 随机种子，保证测试可复现
        """
        self._templates: List[AdTemplate] = templates or []
        self._default_fallback = default_fallback
        self._random_seed = random_seed

        # 合并默认模板
        self._init_templates()

    def _init_templates(self):
        """初始化模板库"""
        # 如果没有自定义模板，使用默认模板
        if not self._templates:
            self._templates = list(DEFAULT_AD_TEMPLATES)
            return

        # 合并默认模板（除非明确禁用）
        if self._default_fallback:
            default_types = {t.type for t in DEFAULT_AD_TEMPLATES}
            existing_types = {t.type for t in self._templates}

            for template in DEFAULT_AD_TEMPLATES:
                if template.type not in existing_types:
                    self._templates.append(template)

    def find_best_match(
        self,
        content: str,
        title: str = "",
        tags: List[str] = None,
    ) -> TemplateMatch:
        """
        找到最匹配的模板

        Args:
            content: 内容文本（正文）
            title: 标题
            tags: 标签列表

        Returns:
            TemplateMatch: 最佳匹配结果
        """
        if tags is None:
            tags = []

        # 合并所有文本用于匹配
        full_text = f"{title} {content} {' '.join(tags)}".lower()

        best_match: Optional[Tuple[AdTemplate, List[str], float]] = None

        for template in self._templates:
            if not template.match_keywords:
                # 跳过空关键词模板（默认兜底）
                continue

            matched = self._find_matched_keywords(template.match_keywords, full_text)
            if not matched:
                continue

            # 计算置信度 = 命中数 / 总关键词数 * 命中密度
            density = len(matched) / len(template.match_keywords)
            confidence = min(density * 1.5, 1.0)  # 最高1.0

            if best_match is None or confidence > best_match[2]:
                best_match = (template, matched, confidence)

        # 命中默认兜底
        if best_match is None:
            default_template = self._get_default_template()
            return TemplateMatch(
                template_type=default_template.type,
                confidence=0.1,
                matched_keywords=[],
                strategy=TemplateMatchStrategy.RANDOM,
            )

        template, matched, confidence = best_match
        return TemplateMatch(
            template_type=template.type,
            confidence=confidence,
            matched_keywords=matched,
            strategy=TemplateMatchStrategy.KEYWORD,
        )

    def _find_matched_keywords(
        self, keywords: List[str], text: str
    ) -> List[str]:
        """查找文本中匹配的关键词"""
        matched = []
        for kw in keywords:
            # 支持中英文关键词
            if kw.lower() in text:
                matched.append(kw)
        return matched

    def _get_default_template(self) -> AdTemplate:
        """获取默认兜底模板"""
        for template in self._templates:
            if template.type == AdTemplateType.DEFAULT:
                return template
        # 兜底兜底
        return AdTemplate(
            type=AdTemplateType.DEFAULT,
            name="通用推广",
            description="兜底模板",
            match_keywords=[],
            template=DEFAULT_AD_TEMPLATES[-1].template,
            contrast_point="",
            emoji="🌱",
        )

    def generate_ad(
        self,
        content: str,
        title: str = "",
        tags: List[str] = None,
        link: str = "",
        summary: str = "",
    ) -> Tuple[str, TemplateMatch]:
        """
        生成软广文本

        Args:
            content: 内容文本
            title: 标题
            tags: 标签列表
            link: 推广链接
            summary: 摘要（用于默认模板）

        Returns:
            Tuple[软广文本, 匹配结果]
        """
        match = self.find_best_match(content, title, tags)

        # 找到对应模板
        template = self._find_template_by_type(match.template_type)
        if template is None:
            template = self._get_default_template()

        # 生成文本
        ad_text = template.generate(
            title=title,
            summary=summary or content[:200],
            link=link,
            tags=tags or [],
        )

        return ad_text, match

    def _find_template_by_type(
        self, template_type: AdTemplateType
    ) -> Optional[AdTemplate]:
        """根据类型查找模板"""
        for template in self._templates:
            if template.type == template_type:
                return template
        return None

    def pick_ad_template(self, tags: List[str]) -> AdTemplate:
        """
        根据标签选择模板（简化版API）

        等价于 find_best_match("", "", tags)[0] 对应模板

        Args:
            tags: 标签列表

        Returns:
            AdTemplate: 选中的模板
        """
        match = self.find_best_match("", "", tags)
        template = self._find_template_by_type(match.template_type)
        if template is None:
            template = self._get_default_template()
        return template

    def generate_multiple_variants(
        self,
        content: str,
        title: str = "",
        tags: List[str] = None,
        link: str = "",
        summary: str = "",
        count: int = 3,
    ) -> List[Tuple[str, TemplateMatch]]:
        """
        生成多个软广变体（A/B测试用）

        Args:
            content: 内容文本
            title: 标题
            tags: 标签列表
            link: 推广链接
            summary: 摘要
            count: 生成数量

        Returns:
            List[ Tuple[软广文本, 匹配结果] ]
        """
        results = []

        # 1. 最佳匹配
        best_text, best_match = self.generate_ad(
            content, title, tags, link, summary
        )
        results.append((best_text, best_match))

        # 2. 随机变体（排除最佳）
        available = [t for t in self._templates if t.type != best_match.template_type]
        if available:
            random.shuffle(available)
            for template in available[:count - 1]:
                ad_text = template.generate(
                    title=title,
                    summary=summary or content[:200],
                    link=link,
                    tags=tags or [],
                )
                results.append((
                    ad_text,
                    TemplateMatch(
                        template_type=template.type,
                        confidence=0.5,
                        matched_keywords=[],
                        strategy=TemplateMatchStrategy.RANDOM,
                    )
                ))

        return results[:count]

    @staticmethod
    def content_hash(content: str, title: str = "") -> str:
        """计算内容哈希（用于去重）"""
        text = f"{title}:{content}".encode("utf-8")
        return hashlib.sha256(text).hexdigest()[:16]

    def get_templates(self) -> List[Dict[str, Any]]:
        """获取所有模板信息"""
        return [t.to_dict() for t in self._templates]

    def get_template_stats(self) -> Dict[str, Any]:
        """获取模板统计"""
        stats = {}
        for template in self._templates:
            stats[template.type.value] = {
                "name": template.name,
                "keywords_count": len(template.match_keywords),
                "description": template.description,
            }
        return stats


# 全局单例
_engine_instance: Optional[TemplateEngine] = None


def get_template_engine() -> TemplateEngine:
    """获取模板引擎全局实例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = TemplateEngine()
    return _engine_instance
