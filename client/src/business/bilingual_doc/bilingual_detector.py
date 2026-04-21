"""
Bilingual Detector - 智能双语判断器
=====================================

核心创新：智能推断文档是否需要双语对照

判断依据：
1. 语言一致性 - 文档是否为单语/双语混杂
2. 目标读者 - 学术/专业文档可能需要双语
3. 内容类型 - 技术文档/教程/论文等
4. 专业术语密度 - 高术语密度建议双语
5. 用户偏好设置
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
from collections import Counter


class Language(Enum):
    """支持的语言"""
    ZH = "zh"       # 中文
    EN = "en"       # 英文
    JA = "ja"       # 日语
    KO = "ko"       # 韩语
    FR = "fr"       # 法语
    DE = "de"       # 德语
    ES = "es"       # 西班牙语
    RU = "ru"       # 俄语
    AR = "ar"       # 阿拉伯语
    MULTI = "multi" # 多语混合
    UNKNOWN = "unknown"


class ContentType(Enum):
    """内容类型"""
    ACADEMIC_PAPER = "academic_paper"       # 学术论文
    TECHNICAL_DOC = "technical_doc"          # 技术文档
    TUTORIAL = "tutorial"                   # 教程
    NEWS = "news"                            # 新闻
    BUSINESS = "business"                    # 商业文档
    LEGAL = "legal"                          # 法律文档
    MARKETING = "marketing"                  # 营销文档
    PERSONAL = "personal"                   # 个人文档
    CODE_DOC = "code_doc"                    # 代码文档
    GENERAL = "general"                      # 一般文本


class BilingualNeed(Enum):
    """双语需求程度"""
    REQUIRED = "required"      # 必须双语
    RECOMMENDED = "recommended"  # 建议双语
    OPTIONAL = "optional"       # 可选
    NOT_NEEDED = "not_needed"   # 不需要


@dataclass
class LanguageProfile:
    """语言画像"""
    primary_language: Language
    language_ratio: Dict[Language, float]  # 各语言占比
    is_mixed: bool                           # 是否多语混合
    confidence: float = 1.0


@dataclass
class ContentProfile:
    """内容画像"""
    content_type: ContentType
    technical_level: float  # 技术难度 0-1
    terminology_density: float  # 术语密度 0-1
    formal_score: float  # 正式程度 0-1
    estimated_reader_level: str  # 目标读者水平


@dataclass
class BilingualDecision:
    """双语决策结果"""
    need_level: BilingualNeed
    confidence: float
    reasons: List[str]
    source_lang: Language
    target_lang: Language
    language_profile: Optional[LanguageProfile] = None
    content_profile: Optional[ContentProfile] = None
    alternative_suggestions: List[str] = field(default_factory=list)

    def should_translate(self) -> bool:
        """是否应该翻译"""
        return self.need_level in (BilingualNeed.REQUIRED, BilingualNeed.RECOMMENDED)

    def should_bilingual(self) -> bool:
        """是否应该双语对照"""
        return self.need_level == BilingualNeed.REQUIRED


class BilingualDetector:
    """智能双语判断器"""

    # 中文检测
    ZH_PATTERN = re.compile(r'[\u4e00-\u9fff]')
    # 日语检测 (平假名 + 片假名)
    JA_PATTERN = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')
    # 韩语检测
    KO_PATTERN = re.compile(r'[\uac00-\ud7af]')
    # 阿拉伯语检测
    AR_PATTERN = re.compile(r'[\u0600-\u06ff]')
    # 西里尔字母 (俄语等)
    CYRILLIC_PATTERN = re.compile(r'[\u0400-\u04ff]')

    # 技术文档关键词
    TECHNICAL_KEYWORDS = [
        'algorithm', 'function', 'method', 'class', 'module', 'api',
        'interface', 'protocol', 'database', 'server', 'client',
        '代码', '算法', '函数', '类', '模块', '接口', '协议', '数据库',
        'installation', 'configuration', 'setup', 'deployment',
        '安装', '配置', '部署', '教程', 'guide', 'tutorial'
    ]

    # 学术论文关键词
    ACADEMIC_KEYWORDS = [
        'abstract', 'introduction', 'methodology', 'results', 'conclusion',
        '参考文献', '摘要', '引言', '方法', '结果', '结论',
        'abstract', 'introduction', 'conclusion', 'references',
        'figure', 'table', 'experiment', 'analysis'
    ]

    # 代码文档关键词
    CODE_DOC_KEYWORDS = [
        'def ', 'class ', 'import ', 'from ', 'const ', 'let ', 'var ',
        'function', 'return', 'if __name__', 'public static void',
        '```python', '```javascript', '```java', '```cpp'
    ]

    # 高密度术语领域
    TERMINOLOGY_DOMAINS = {
        'legal': ['contract', 'agreement', 'party', 'liability', 'obligation', 'contract'],
        'medical': ['patient', 'diagnosis', 'treatment', 'symptom', 'prescription'],
        'technical': ['protocol', 'specification', 'implementation', 'architecture'],
        'academic': ['hypothesis', 'methodology', 'correlation', 'significance']
    }

    def __init__(self):
        self.default_source_lang = Language.EN
        self.default_target_lang = Language.ZH

    def analyze(self, text: str, file_path: Optional[str] = None,
                user_preference: Optional[BilingualNeed] = None) -> BilingualDecision:
        """
        智能分析是否需要双语对照

        Args:
            text: 文档文本内容
            file_path: 文件路径（用于辅助判断）
            user_preference: 用户偏好设置

        Returns:
            BilingualDecision: 双语决策结果
        """
        if not text or len(text.strip()) < 50:
            return BilingualDecision(
                need_level=BilingualNeed.OPTIONAL,
                confidence=0.5,
                reasons=["文档内容过短，无法准确判断"],
                source_lang=Language.UNKNOWN,
                target_lang=self.default_target_lang
            )

        # 1. 语言分析
        lang_profile = self._analyze_language(text)

        # 2. 内容分析
        content_profile = self._analyze_content(text, file_path)

        # 3. 决策生成
        decision = self._make_decision(lang_profile, content_profile, user_preference)

        return decision

    def _analyze_language(self, text: str) -> LanguageProfile:
        """分析文档语言特征"""
        # 统计各语言字符数
        lang_chars = {
            Language.ZH: len(self.ZH_PATTERN.findall(text)),
            Language.JA: len(self.JA_PATTERN.findall(text)),
            Language.KO: len(self.KO_PATTERN.findall(text)),
            Language.AR: len(self.AR_PATTERN.findall(text)),
        }

        # 检测西里尔字母
        cyrillic_count = len(self.CYRILLIC_PATTERN.findall(text))
        if cyrillic_count > 0:
            lang_chars[Language.RU] = cyrillic_count

        # 英文检测 (基于 ASCII 字母)
        en_chars = len(re.findall(r'[a-zA-Z]', text))
        if en_chars > 0:
            lang_chars[Language.EN] = en_chars

        total_chars = len(text)
        if total_chars == 0:
            return LanguageProfile(
                primary_language=Language.UNKNOWN,
                language_ratio={},
                is_mixed=False,
                confidence=0.0
            )

        # 计算语言比例
        lang_ratio = {lang: count / total_chars for lang, count in lang_chars.items()}
        lang_ratio = {k: v for k, v in lang_ratio.items() if v > 0.01}  # 过滤噪音

        # 确定主要语言
        if not lang_ratio:
            primary = Language.UNKNOWN
        else:
            primary = max(lang_ratio, key=lang_ratio.get)

        # 判断是否多语混合
        significant_langs = [k for k, v in lang_ratio.items() if v > 0.05]
        is_mixed = len(significant_langs) >= 2

        return LanguageProfile(
            primary_language=primary,
            language_ratio=lang_ratio,
            is_mixed=is_mixed,
            confidence=lang_ratio.get(primary, 0) if primary != Language.UNKNOWN else 0.5
        )

    def _analyze_content(self, text: str, file_path: Optional[str]) -> ContentProfile:
        """分析文档内容类型"""
        text_lower = text.lower()

        # 检测内容类型
        content_type = self._detect_content_type(text_lower, text)

        # 计算技术难度 (基于句子复杂度)
        technical_level = self._calculate_technical_level(text_lower)

        # 计算术语密度
        terminology_density = self._calculate_terminology_density(text_lower)

        # 计算正式程度
        formal_score = self._calculate_formal_score(text_lower)

        # 估计读者水平
        reader_level = self._estimate_reader_level(
            content_type, technical_level, terminology_density
        )

        return ContentProfile(
            content_type=content_type,
            technical_level=technical_level,
            terminology_density=terminology_density,
            formal_score=formal_score,
            estimated_reader_level=reader_level
        )

    def _detect_content_type(self, text_lower: str, text: str) -> ContentType:
        """检测内容类型"""
        # 检查学术论文特征
        academic_matches = sum(1 for kw in self.ACADEMIC_KEYWORDS if kw in text_lower)
        if academic_matches >= 3 or text_lower.strip().startswith('abstract'):
            return ContentType.ACADEMIC_PAPER

        # 检查代码文档特征
        code_matches = sum(1 for kw in self.CODE_DOC_KEYWORDS if kw in text_lower)
        if code_matches >= 2:
            return ContentType.CODE_DOC

        # 检查技术文档特征
        tech_matches = sum(1 for kw in self.TECHNICAL_KEYWORDS if kw in text_lower)
        if tech_matches >= 3:
            return ContentType.TECHNICAL_DOC

        # 检查教程特征
        tutorial_keywords = ['how to', 'step by step', 'tutorial', '入门', '教程', '学习']
        if any(kw in text_lower for kw in tutorial_keywords):
            return ContentType.TUTORIAL

        # 检查商业文档
        business_keywords = ['company', 'revenue', 'market', 'customer', '公司', '市场', '客户', '营收']
        if any(kw in text_lower for kw in business_keywords):
            return ContentType.BUSINESS

        # 检查法律文档
        legal_keywords = ['contract', 'agreement', 'party', 'liability', '条款', '协议', '甲方', '乙方']
        if any(kw in text_lower for kw in legal_keywords):
            return ContentType.LEGAL

        # 检查新闻
        news_keywords = ['reported', 'announced', 'said', 'according to', '报道', '宣布', '据悉']
        if any(kw in text_lower for kw in news_keywords):
            return ContentType.NEWS

        return ContentType.GENERAL

    def _calculate_technical_level(self, text_lower: str) -> float:
        """计算技术难度"""
        score = 0.0

        # 句子长度指标 (长句通常更技术性)
        sentences = re.split(r'[.!?。！？]', text_lower)
        if sentences:
            avg_sentence_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        else:
            avg_sentence_len = 0

        if avg_sentence_len > 25:
            score += 0.3
        elif avg_sentence_len > 15:
            score += 0.2
        elif avg_sentence_len > 8:
            score += 0.1

        # 缩略词密度
        acronyms = re.findall(r'\b[A-Z]{2,}\b', text_lower)
        if acronyms:
            score += min(0.3, len(acronyms) / 100)

        # 公式和特殊字符
        formula_chars = len(re.findall(r'[=+\-*/<>]', text_lower))
        if formula_chars > 5:
            score += 0.2

        # 数字比例
        numbers = re.findall(r'\d+', text_lower)
        if len(numbers) > 10:
            score += 0.2

        return min(1.0, score)

    def _calculate_terminology_density(self, text_lower: str) -> float:
        """计算术语密度"""
        total_terms = 0
        total_words = len(text_lower.split())

        # 检查各领域术语
        for domain, keywords in self.TERMINOLOGY_DOMAINS.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            total_terms += matches

        # 额外统计
        for kw in self.TECHNICAL_KEYWORDS:
            if kw in text_lower:
                total_terms += 1

        if total_words == 0:
            return 0.0

        density = total_terms / max(total_words / 100, 1)  # 每100词的术语数
        return min(1.0, density / 10)  # 归一化

    def _calculate_formal_score(self, text_lower: str) -> float:
        """计算正式程度"""
        score = 0.5  # 默认中等正式

        # 非正式词汇
        informal_words = ['hey', 'gonna', 'wanna', 'cool', 'awesome', 'lol',
                         '嘿', '哇', '哈哈', '搞定', '牛', '赞']
        informal_count = sum(1 for w in informal_words if w in text_lower)
        if informal_count > 0:
            score -= 0.1 * informal_count

        # 正式词汇
        formal_words = ['therefore', 'hence', 'thus', 'consequently', 'however',
                       '因此', '故', '然而', '综上所述', '基于', '鉴于']
        formal_count = sum(1 for w in formal_words if w in text_lower)
        if formal_count > 0:
            score += 0.1 * formal_count

        # 人称 (第一人称通常更非正式)
        first_person = len(re.findall(r'\b(i|me|my|we|our|us)\b', text_lower))
        if first_person > 5:
            score -= 0.1

        return max(0.0, min(1.0, score))

    def _estimate_reader_level(self, content_type: ContentType,
                               technical_level: float,
                               terminology_density: float) -> str:
        """估计目标读者水平"""
        if content_type == ContentType.ACADEMIC_PAPER:
            return "expert"
        if content_type == ContentType.TUTORIAL:
            if technical_level < 0.3:
                return "beginner"
            return "intermediate"
        if content_type == ContentType.CODE_DOC:
            return "intermediate"
        if terminology_density > 0.6 or technical_level > 0.6:
            return "advanced"
        return "general"

    def _make_decision(self, lang_profile: LanguageProfile,
                      content_profile: ContentProfile,
                      user_preference: Optional[BilingualNeed]) -> BilingualDecision:
        """生成双语决策"""

        reasons = []
        need_score = 0.0  # 0-1 分数越高越需要双语

        # 因素1: 如果文档已经是双语混杂，无需再翻译
        if lang_profile.is_mixed:
            reasons.append("文档已包含多语言内容")
            return BilingualDecision(
                need_level=BilingualNeed.NOT_NEEDED,
                confidence=0.8,
                reasons=reasons,
                source_lang=lang_profile.primary_language,
                target_lang=self.default_target_lang,
                language_profile=lang_profile,
                content_profile=content_profile
            )

        # 因素2: 语言本身的特点
        source_lang = lang_profile.primary_language
        if source_lang == Language.EN:
            # 英文 -> 中文翻译需求较高
            need_score += 0.3
            reasons.append("英文文档，目标读者可能需要中文对照")
        elif source_lang == Language.ZH:
            # 中文 -> 英文翻译需求中等
            need_score += 0.2
            reasons.append("中文文档，可能需要英文版本")
        elif source_lang == Language.JA or source_lang == Language.KO:
            need_score += 0.25
            reasons.append("日/韩语文档，翻译难度较高")
        elif source_lang == Language.UNKNOWN:
            need_score += 0.1
            reasons.append("无法确定源语言，建议双语")

        # 因素3: 内容类型
        if content_profile.content_type == ContentType.ACADEMIC_PAPER:
            need_score += 0.4
            reasons.append("学术论文通常需要双语对照便于理解")
        elif content_profile.content_type == ContentType.TECHNICAL_DOC:
            need_score += 0.35
            reasons.append("技术文档术语密集，双语有助于理解")
        elif content_profile.content_type == ContentType.TUTORIAL:
            need_score += 0.25
            reasons.append("教程类文档双语便于学习")
        elif content_profile.content_type == ContentType.CODE_DOC:
            need_score += 0.2
            reasons.append("代码文档可选择性双语")

        # 因素4: 技术难度
        if content_profile.technical_level > 0.6:
            need_score += 0.2
            reasons.append("高技术难度内容需要双语降低理解门槛")
        elif content_profile.technical_level < 0.2:
            need_score -= 0.1
            reasons.append("内容相对简单，可选双语")

        # 因素5: 术语密度
        if content_profile.terminology_density > 0.5:
            need_score += 0.2
            reasons.append("高术语密度，专业对照有价值")
        elif content_profile.terminology_density > 0.3:
            need_score += 0.1

        # 因素6: 正式程度
        if content_profile.formal_score > 0.7:
            need_score += 0.1
            reasons.append("正式文档双语更专业")

        # 归一化
        need_score = max(0.0, min(1.0, need_score))

        # 考虑用户偏好
        if user_preference:
            if user_preference == BilingualNeed.REQUIRED:
                need_score = max(need_score, 0.7)
            elif user_preference == BilingualNeed.NOT_NEEDED:
                need_score = min(need_score, 0.3)

        # 生成决策
        if need_score >= 0.65:
            need_level = BilingualNeed.REQUIRED
        elif need_score >= 0.45:
            need_level = BilingualNeed.RECOMMENDED
        elif need_score >= 0.25:
            need_level = BilingualNeed.OPTIONAL
        else:
            need_level = BilingualNeed.NOT_NEEDED

        # 生成建议
        suggestions = []
        if content_profile.content_type == ContentType.ACADEMIC_PAPER:
            suggestions.append("建议生成双语对照 PDF，包含摘要的完整翻译")
        elif content_profile.content_type == ContentType.TECHNICAL_DOC:
            suggestions.append("建议生成双语对照，保留原文术语对照表")
        elif content_profile.content_type == ContentType.TUTORIAL:
            suggestions.append("可选双语，若只需一种语言建议仅译文")

        # 确定目标语言
        if source_lang == Language.EN:
            target_lang = Language.ZH
        elif source_lang == Language.ZH:
            target_lang = Language.EN
        else:
            target_lang = Language.ZH  # 默认翻译为中文

        return BilingualDecision(
            need_level=need_level,
            confidence=min(0.95, need_score + 0.2),  # 置信度
            reasons=reasons,
            source_lang=source_lang,
            target_lang=target_lang,
            language_profile=lang_profile,
            content_profile=content_profile,
            alternative_suggestions=suggestions
        )

    def quick_check(self, text: str) -> Tuple[bool, float]:
        """
        快速检查是否需要双语

        Returns:
            (是否需要双语, 置信度)
        """
        decision = self.analyze(text)
        return decision.should_bilingual(), decision.confidence


# 便捷函数
def should_create_bilingual(text: str, file_path: str = None) -> BilingualDecision:
    """快速判断是否需要双语对照"""
    detector = BilingualDetector()
    return detector.analyze(text, file_path)
