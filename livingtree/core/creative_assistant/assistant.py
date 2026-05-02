"""
智能创作与专业审核增强系统 - 智能创作助手
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ContentType(Enum):
    GENERAL = "general"
    TECHNICAL = "technical"
    BUSINESS = "business"
    CREATIVE = "creative"
    REPORT = "report"


class WritingStyle(Enum):
    FORMAL = "formal"
    INFORMAL = "informal"
    ACADEMIC = "academic"
    TECHNICAL = "technical"
    SIMPLE = "simple"


@dataclass
class WritingContext:
    content_type: ContentType = ContentType.GENERAL
    style: WritingStyle = WritingStyle.FORMAL
    target_audience: str = ""
    purpose: str = ""
    tone: str = "中性"
    domain: str = ""


@dataclass
class WritingSuggestion:
    type: str
    position: int
    length: int
    text: str
    confidence: float
    reason: str


@dataclass
class ContentAnalysis:
    word_count: int = 0
    char_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0
    readability_score: float = 0.0
    quality_score: float = 0.0
    complexity: str = "中等"
    structure_tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    entities: List[Dict] = field(default_factory=list)
    issues: List[Dict] = field(default_factory=list)


class IntelligentWritingAssistant:
    """智能创作助手"""

    def __init__(self):
        self.templates = self._load_templates()
        self.glossary = self._load_glossary()

    def _load_templates(self) -> Dict[str, str]:
        return {
            "report": "# {title}\n\n## 一、概述\n{summary}\n\n## 二、主要内容\n{content}\n\n## 三、结论与建议\n{conclusion}\n",
            "proposal": "# {title}\n\n## 项目背景\n{background}\n\n## 项目目标\n{objectives}\n\n## 实施方案\n{implementation}\n",
            "meeting": "# 会议记录\n\n## 基本信息\n- 时间: {time}\n- 参会人: {attendees}\n\n## 会议议题\n{topics}\n\n## 决议事项\n{decisions}\n",
        }

    def _load_glossary(self) -> Dict[str, str]:
        return {"EIA": "环境影响评价", "ESG": "环境、社会和治理", "KPI": "关键绩效指标"}

    def analyze_content(self, content: str, context: WritingContext = None) -> ContentAnalysis:
        analysis = ContentAnalysis()
        analysis.char_count = len(content)
        analysis.word_count = len(re.findall(r'[\u4e00-\u9fa5]+', content))
        analysis.sentence_count = len(re.findall(r'[.。!！?？]', content))
        analysis.paragraph_count = len([p for p in content.split('\n\n') if p.strip()])

        analysis.structure_tags = self._detect_structure(content)
        analysis.keywords = self._extract_keywords(content)

        if analysis.sentence_count > 0:
            avg_len = analysis.char_count / analysis.sentence_count
            analysis.readability_score = 90 if avg_len < 30 else (75 if avg_len < 50 else 60)

        analysis.issues = self._detect_issues(content)
        analysis.quality_score = min(100, max(0, 80 + analysis.readability_score * 0.2 - len(analysis.issues) * 5))

        return analysis

    def _detect_structure(self, content: str) -> List[str]:
        tags = []
        if re.search(r'^#+\s+', content, re.MULTILINE): tags.append("heading")
        if re.search(r'^\d+\.\s+', content, re.MULTILINE): tags.append("numbered")
        if re.search(r'^[-*]\s+', content, re.MULTILINE): tags.append("bullet")
        if re.search(r'```', content): tags.append("code")
        return tags

    def _extract_keywords(self, content: str) -> List[str]:
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', content)
        freq = {}
        for w in words:
            if len(w) >= 2: freq[w] = freq.get(w, 0) + 1
        return [w for w, c in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10] if c > 1]

    def _detect_issues(self, content: str) -> List[Dict]:
        issues = []
        for i, s in enumerate(re.split(r'[.。!！?？]', content)):
            if len(s) > 100:
                issues.append({"type": "long_sentence", "severity": "minor", "message": f"句子过长({len(s)}字符)"})
        return issues

    def suggest_completion(self, content: str, context: WritingContext = None) -> List[WritingSuggestion]:
        suggestions = []
        if len(content) > 500 and not re.search(r'总结|结论', content[-200:]):
            suggestions.append(WritingSuggestion(
                type="completion", position=len(content), length=50,
                text="\n\n## 结论\n综上所述，...", confidence=0.8,
                reason="内容较长但缺少结论"
            ))
        return suggestions

    def improve_content(self, content: str, context: WritingContext = None) -> str:
        improved = content
        for abbr, full in self.glossary.items():
            improved = improved.replace(abbr, f"{full}({abbr})")
        improved = re.sub(r'\n{3,}', '\n\n', improved)
        improved = re.sub(r' {2,}', ' ', improved)
        return improved

    def generate_from_template(self, template_name: str, params: Dict[str, str]) -> str:
        template = self.templates.get(template_name, "")
        try:
            return template.format(**params)
        except KeyError:
            return "缺少必要参数"

    def summarize_content(self, content: str, max_length: int = 200) -> str:
        sentences = [s.strip() for s in re.split(r'[。.!?]+', content) if len(s.strip()) > 10]
        if not sentences:
            return content[:max_length]

        keywords = self._extract_keywords(content)[:5]
        scored = sorted(sentences, key=lambda s: sum(1 for kw in keywords if kw in s), reverse=True)

        result = ""
        for s in scored:
            if len(result) + len(s) <= max_length:
                result += s + "。"
            else:
                break
        return result or content[:max_length]


class CreativeAssistantSystem:
    """创作辅助系统"""

    def __init__(self):
        self.assistant = create_writing_assistant()
        self.drafts = {}

    def analyze(self, content: str, domain: str = "") -> ContentAnalysis:
        ctx = WritingContext(domain=domain)
        return self.assistant.analyze_content(content, ctx)

    def suggest(self, content: str, domain: str = "") -> List[WritingSuggestion]:
        ctx = WritingContext(domain=domain)
        return self.assistant.suggest_completion(content, ctx)

    def improve(self, content: str, domain: str = "") -> str:
        ctx = WritingContext(domain=domain)
        return self.assistant.improve_content(content, ctx)

    def summarize(self, content: str, max_length: int = 200) -> str:
        return self.assistant.summarize_content(content, max_length)

    def generate(self, template: str, params: Dict) -> str:
        return self.assistant.generate_from_template(template, params)

    def get_templates(self) -> List[str]:
        return list(self.assistant.templates.keys())


def create_writing_assistant() -> IntelligentWritingAssistant:
    return IntelligentWritingAssistant()


def create_creative_assistant_system() -> CreativeAssistantSystem:
    return CreativeAssistantSystem()
