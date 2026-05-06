"""Content Quality — low-quality content filtering + auto-labeling.

P2 准确率提升模块：知识库入库前的质量把关和自动标签生成。

Core techniques:
  Low-quality filter:    空白页检测 / 乱码检测 / 水印检测 / 重复模板
  Quality scoring:       完整性 / 信息密度 / 结构清晰度 / 术语丰富度
  Auto-labeling:         LLM提取主题标签 / 实体类别 / 难度等级
  Content normalization: 编码统一 / 空白规范化 / 特殊字符清理

集成现有:
  - DedupEngine: 去重 (exact/near-hash/semantic)
  - UniversalFileParser: 38格式解析
  - DocumentTree: 结构分析
"""

from __future__ import annotations

import re
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class QualityScore:
    """内容质量评分。"""
    overall: float = 0.0          # 综合得分 0.0-1.0
    completeness: float = 0.0     # 完整性: 是否有头有尾
    information_density: float = 0.0  # 信息密度: 非重复内容比例
    structure_clarity: float = 0.0    # 结构清晰度: 是否有章节/段落
    term_richness: float = 0.0        # 术语丰富度: 专业词汇密度
    issues: list[str] = field(default_factory=list)  # 质量问题列表
    is_acceptable: bool = True


@dataclass
class ContentLabel:
    """自动生成的内容标签。"""
    primary_topic: str = ""
    subtopics: list[str] = field(default_factory=list)
    entity_types: list[str] = field(default_factory=list)
    difficulty: str = "intermediate"  # "basic", "intermediate", "advanced"
    domain: str = ""
    language: str = "zh"
    keywords: list[str] = field(default_factory=list)


class ContentQuality:
    """内容质量过滤器 + 自动标签生成器。

    Usage:
        cq = ContentQuality()
        score = cq.evaluate(document_text)
        if not score.is_acceptable:
            logger.warning(f"Low quality content: {score.issues}")

        label = cq.auto_label(document_text, title="环评报告")
    """

    def __init__(self, min_quality_score: float = 0.3):
        self.min_quality_score = min_quality_score
        self._label_cache: dict[str, ContentLabel] = {}

    def evaluate(self, text: str, title: str = "") -> QualityScore:
        """评估内容质量并标记问题。"""
        score = QualityScore()

        if not text or len(text) < 20:
            score.issues.append("empty_or_too_short")
            score.is_acceptable = False
            return score

        score.completeness = self._score_completeness(text)
        score.information_density = self._score_density(text)
        score.structure_clarity = self._score_structure(text)
        score.term_richness = self._score_terms(text)

        # Penalties
        if self._is_empty_template(text):
            score.issues.append("empty_template")
            score.information_density *= 0.3

        if self._is_scanned_watermark(text):
            score.issues.append("watermark_detected")
            score.completeness *= 0.5

        if self._has_repeating_patterns(text):
            score.issues.append("repeating_pattern")
            score.information_density *= 0.5

        score.overall = (
            score.completeness * 0.20 +
            score.information_density * 0.35 +
            score.structure_clarity * 0.25 +
            score.term_richness * 0.20
        )

        score.is_acceptable = score.overall >= self.min_quality_score and len(score.issues) < 3

        if not score.is_acceptable:
            logger.debug("ContentQuality: rejected '%s' (score=%.2f, issues=%s)",
                        title, score.overall, score.issues)

        return score

    def filter(self, texts: list[tuple[str, str]]) -> list[tuple[str, str, QualityScore]]:
        """批量质量过滤。返回通过的内容及评分。"""
        results = []
        for text, title in texts:
            score = self.evaluate(text, title)
            if score.is_acceptable:
                results.append((text, title, score))
            else:
                logger.info("ContentQuality: filtered out '%s' — %s", title, score.issues)
        return results

    def auto_label(self, text: str, title: str = "", hub: Any = None) -> ContentLabel:
        """自动生成内容标签。

        规则优先（快速），LLM补充（精准）。
        """
        label = ContentLabel()

        if title:
            label_cache_key = title[:100]
            if label_cache_key in self._label_cache:
                return self._label_cache[label_cache_key]

        label.language = self._detect_language(text)
        label.primary_topic = self._extract_primary_topic(text, title)
        label.subtopics = self._extract_subtopics(text)
        label.keywords = self._extract_keywords_from_text(text)
        label.entity_types = self._classify_entity_types(text)
        label.difficulty = self._assess_difficulty(text)
        label.domain = self._detect_domain(text, title)

        if hub:
            try:
                llm_label = self._llm_label(text[:2000], title, hub)
                if llm_label.primary_topic:
                    label = llm_label
            except Exception as e:
                logger.debug("LLM labeling failed: %s", e)

        if title:
            self._label_cache[title[:100]] = label

        return label

    def batch_label(self, items: list[tuple[str, str]], hub: Any = None) -> list[ContentLabel]:
        """批量自动标签。"""
        return [self.auto_label(text, title, hub) for text, title in items]

    # ── Quality scoring sub-functions ──

    @staticmethod
    def _score_completeness(text: str) -> float:
        score = 0.0

        sentences = re.split(r'[。！？\n.!?]+', text)
        if len(sentences) >= 3:
            score += 0.3

        first_sentence = sentences[0].strip() if sentences else ""
        last_sentence = sentences[-1].strip() if len(sentences) > 1 else ""
        if len(first_sentence) > 10:
            score += 0.2
        if len(last_sentence) > 10 and last_sentence != first_sentence:
            score += 0.2

        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        if len(paragraphs) >= 2:
            score += 0.3

        return min(1.0, score)

    @staticmethod
    def _score_density(text: str) -> float:
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)
        if not words:
            return 0.0

        unique = len(set(w.lower() for w in words))
        total = len(words)
        type_token_ratio = unique / max(total, 1)

        nonspace = len(re.sub(r'\s', '', text))
        density = nonspace / max(len(text), 1)

        return (type_token_ratio * 0.6 + density * 0.4)

    @staticmethod
    def _score_structure(text: str) -> float:
        score = 0.0

        if re.search(r'^#{1,3}\s', text, re.MULTILINE):
            score += 0.3

        if re.search(r'^[第].*?[章節节]', text, re.MULTILINE):
            score += 0.3

        paragraphs = [p for p in text.split('\n\n') if len(p.strip()) > 30]
        if len(paragraphs) >= 3:
            score += 0.2

        lists = re.findall(r'^[\d]+[\.\、\)]|^[-*•]', text, re.MULTILINE)
        if len(lists) >= 3:
            score += 0.2

        return min(1.0, score)

    @staticmethod
    def _score_terms(text: str) -> float:
        tech_patterns = [
            r'(?:GB|HJ|ISO|IEEE)\s*[\d\.\-]+',
            r'(?:第[一二三四五六七八九十]+[章節条])\s',
            r'(?:参数|系数|指标|阈值|标准|规范|规程)',
        ]
        count = sum(len(re.findall(p, text)) for p in tech_patterns)
        length_factor = max(len(text) / 1000, 0.1)
        return min(1.0, count / (10 * length_factor))

    # ── Issue detection ──

    @staticmethod
    def _is_empty_template(text: str) -> bool:
        patterns = [
            r'此处填写|请在此输入|点击添加|placeholder|模板内容',
            r'^\s*\{\{.*?\}\}\s*$',
        ]
        return any(re.search(p, text) for p in patterns)

    @staticmethod
    def _is_scanned_watermark(text: str) -> bool:
        watermarks = ['仅供内部', '机密', 'CONFIDENTIAL', 'DRAFT', '草稿',
                      '评估专用', '复印件', 'COPY']
        return sum(1 for w in watermarks if w in text) >= 2

    @staticmethod
    def _has_repeating_patterns(text: str) -> bool:
        lines = text.split('\n')
        if len(lines) < 5:
            return False
        counter = Counter(line.strip() for line in lines if len(line.strip()) > 5)
        for line, count in counter.most_common(3):
            if count >= 3 and len(line) > 10:
                return True
        return False

    # ── Label generation ──

    @staticmethod
    def _detect_language(text: str) -> str:
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        total = len(text) or 1
        if chinese / total > 0.3:
            return "zh"
        return "en"

    @staticmethod
    def _extract_primary_topic(text: str, title: str = "") -> str:
        if title:
            return title[:50]
        first_line = text.split('\n')[0].strip()
        if len(first_line) < 100:
            return re.sub(r'^[#\s\d\.]+', '', first_line).strip()[:50]
        return ""

    @staticmethod
    def _extract_subtopics(text: str) -> list[str]:
        headings = re.findall(r'^#{1,3}\s+(.+)$', text, re.MULTILINE)
        headings += re.findall(r'^[第].*?[章節节]\s*(.*)', text, re.MULTILINE)
        return list(dict.fromkeys(h.strip()[:60] for h in headings[:5]))

    @staticmethod
    def _extract_keywords_from_text(text: str) -> list[str]:
        words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        counter = Counter(w for w in words if len(w) >= 2)
        stopwords = {'的是', '一个', '这个', '那个', '可以', '进行', '使用', '通过',
                    '没有', '不是', '以及', '或者', '但是', '因此', '所以', '如果',
                    '已经', '具有', '对于', '根据', '按照', '其中', '包括', '主要'}
        filtered = [(w, c) for w, c in counter.most_common(20) if w not in stopwords]
        return [w for w, _ in filtered[:8]]

    @staticmethod
    def _classify_entity_types(text: str) -> list[str]:
        types = []
        if re.search(r'(?:公司|企业|工厂|集团|项目)', text):
            types.append("organization")
        if re.search(r'(?:GB|HJ|ISO|标准|规范|规程)', text):
            types.append("standard")
        if re.search(r'(?:模型|算法|公式|系数|参数)', text):
            types.append("technical")
        if re.search(r'(?:监测|检测|采样|分析|评估)', text):
            types.append("measurement")
        if re.search(r'(?:法律|法规|条例|办法|规定)', text):
            types.append("regulation")
        return types or ["general"]

    @staticmethod
    def _assess_difficulty(text: str) -> str:
        score = 0
        score += len(re.findall(r'(?:模型|算法|公式|理论|原理)', text)) * 2
        score += len(re.findall(r'(?:系数|参数|阈值|指标)', text))
        score += len(re.findall(r'(?:{[\u4e00-\u9fff]+}|[A-Z][a-z]+)', text))
        factor = max(len(text) / 1000, 0.1)
        normalized = score / factor
        if normalized > 10:
            return "advanced"
        elif normalized > 3:
            return "intermediate"
        return "basic"

    @staticmethod
    def _detect_domain(text: str, title: str = "") -> str:
        combined = (title + " " + text[:500]).lower()
        domains = {
            "environmental": ["环评", "环境", "大气", "噪声", "水污染", "排放"],
            "software": ["代码", "编程", "软件", "系统", "API"],
            "legal": ["法律", "法规", "条例", "合同", "知识产权"],
            "engineering": ["工程", "建筑", "施工", "设计", "结构"],
            "data_science": ["数据", "模型", "训练", "AI", "机器学习"],
        }
        for domain, keywords in domains.items():
            if any(kw in combined for kw in keywords):
                return domain
        return "general"

    def _llm_label(self, text: str, title: str, hub: Any) -> ContentLabel:
        prompt = f"""Analyze this document and return a JSON label:
{{
  "primary_topic": "main topic (1-5 words)",
  "subtopics": ["subtopic1", "subtopic2"],
  "domain": "environmental/software/legal/engineering/data_science/general",
  "difficulty": "basic/intermediate/advanced",
  "keywords": ["keyword1", "keyword2", "keyword3"]
}}

Title: {title}
Content: {text[:1500]}"""

        try:
            response = hub.chat(prompt)
            import json
            if '{' in response:
                response = response[response.index('{'):response.rindex('}')+1]
            data = json.loads(response)
            return ContentLabel(
                primary_topic=data.get("primary_topic", ""),
                subtopics=data.get("subtopics", []),
                domain=data.get("domain", "general"),
                difficulty=data.get("difficulty", "intermediate"),
                keywords=data.get("keywords", []),
            )
        except Exception:
            return ContentLabel()
