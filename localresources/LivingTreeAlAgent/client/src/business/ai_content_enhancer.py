"""
AI驱动的主动内容增强系统
AI-Driven Proactive Content Enhancement System

核心功能:
1. 内容智能摘要
2. 代码提取与高亮
3. 关键概念提取
4. 相关资源推荐
5. 隐私参数剥离
6. 知识图谱构建

Author: Hermes Desktop Team
"""

import re
import time
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import threading


# ============================================================
# 第一部分：配置与枚举
# ============================================================

class ContentType(Enum):
    """内容类型"""
    HTML = "html"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"
    CODE = "code"
    PDF = "pdf"
    DOCUMENT = "document"
    UNKNOWN = "unknown"


class EnhancementType(Enum):
    """增强类型"""
    SUMMARY = "summary"
    TRANSLATION = "translation"
    CODE_EXTRACTION = "code"
    KEY_CONCEPTS = "concepts"
    RELATED_LINKS = "related"
    PRIVACY_CLEAN = "privacy"
    KNOWLEDGE_GRAPH = "kg"


@dataclass
class ExtractedCode:
    """提取的代码"""
    code: str
    language: str
    filename: Optional[str] = None
    line_start: int = 0
    line_end: int = 0
    relevance_score: float = 0.0


@dataclass
class ContentEnhancement:
    """内容增强结果"""
    original_content: str
    enhanced_content: str
    content_type: ContentType
    enhancements_applied: List[EnhancementType] = field(default_factory=list)
    summary: str = ""
    extracted_code: List[ExtractedCode] = field(default_factory=list)
    key_concepts: List[str] = field(default_factory=list)
    related_links: List[str] = field(default_factory=list)
    privacy_cleaned: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# 第二部分：隐私清理器
# ============================================================

class PrivacyCleaner:
    """隐私参数清理器"""

    TRACKING_PARAMS = {
        r'utm_source', r'utm_medium', r'utm_campaign', r'utm_term', r'utm_content',
        r'fbclid', r'fb_action_ids', r'fb_action_types', r'fb_source', r'fb_ref',
        r'gclid', r'gclsrc', r'dclid', r'zanpid',
        r'src', r'ref_src', r'ref_url',
        r'mc_eid', r'mc_cid', r'oly_enc_id', r'oly_anon_id',
        r'redir', r'redirect', r'returnTo',
        r'share_source', r'share_medium',
    }

    SAFE_PARAMS = {
        'q', 'query', 'search', 'keyword',
        'page', 'p', 'offset', 'limit',
        'sort', 'order', 'filter',
        'lang', 'locale', 'region',
        'id', 'pid', 'aid',
    }

    def __init__(self):
        self.pattern = re.compile(
            r'(' + '|'.join(self.TRACKING_PARAMS) + r')=[^&\s]*',
            re.IGNORECASE
        )
        print("[PrivacyCleaner] 初始化隐私清理器")

    def clean_url(self, url: str) -> str:
        """清理URL中的追踪参数"""
        cleaned = self.pattern.sub('', url)

        if '?' in cleaned:
            base, query = cleaned.split('?', 1)
            params = []
            for param in query.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    if key.lower() in self.SAFE_PARAMS or key.lower()[:2] == 'id':
                        params.append(param)
            query = '&'.join(params)
            cleaned = f"{base}?{query}" if params else base

        return cleaned

    def clean_content(self, content: str) -> str:
        """清理内容中的隐私信息"""
        content = re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', '[email]', content)
        content = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[phone]', content)
        content = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[ip]', content)
        return content


# ============================================================
# 第三部分：代码提取器
# ============================================================

class CodeExtractor:
    """代码提取器"""

    LANGUAGE_PATTERNS = {
        'python': [r'\bdef\s+\w+', r'\bimport\s+\w+', r'\bclass\s+\w+.*:', r'if __name__'],
        'javascript': [r'\bfunction\s+\w+', r'\bconst\s+\w+\s*=', r'\blet\s+\w+\s*=', r'=>'],
        'typescript': [r':\s*(string|number|boolean|any)\b', r'interface\s+\w+', r'type\s+\w+\s*='],
        'java': [r'\bpublic\s+(class|static|void)\b', r'\bSystem\.out\.print', r'@Override'],
        'go': [r'\bfunc\s+\w+', r'\bpackage\s+\w+', r'\bimport\s+\(', r':='],
        'rust': [r'\bfn\s+\w+', r'\blet\s+mut\b', r'\bimpl\s+\w+', r'pub\s+fn'],
        'html': [r'<\w+[^>]*>', r'</\w+>', r'<!DOCTYPE'],
        'css': [r'\b[\w-]+\s*:\s*[^;]+;', r'\.\w+\s*{', r'#\w+\s*{'],
        'sql': [r'\bSELECT\b.*\bFROM\b', r'\bINSERT\s+INTO\b', r'\bUPDATE\b.*\bSET\b'],
        'bash': [r'^#!/.+bash', r'\becho\b', r'\bexport\b', r'\bif\s+\[', r'\$\{?\w+\}?'],
    }

    CODE_BLOCK_PATTERN = re.compile(
        r'```(\w*)\n(.*?)```',
        re.DOTALL | re.MULTILINE
    )

    def __init__(self):
        self.language_patterns = {
            lang: re.compile('|'.join(patterns), re.MULTILINE)
            for lang, patterns in self.LANGUAGE_PATTERNS.items()
        }
        print("[CodeExtractor] 初始化代码提取器")

    def extract(self, content: str) -> List[ExtractedCode]:
        """提取代码片段"""
        extracted = []

        for match in self.CODE_BLOCK_PATTERN.finditer(content):
            lang = match.group(1) or 'plain'
            code = match.group(2).strip()

            if len(code) > 20:
                extracted.append(ExtractedCode(
                    code=code,
                    language=lang,
                    relevance_score=self._calculate_relevance(code, lang)
                ))

        inline_pattern = re.compile(r'`([^`]+)`')
        for match in inline_pattern.finditer(content):
            code = match.group(1)
            if len(code) > 30 and '\n' in code:
                lang = self._detect_language(code)
                if lang:
                    extracted.append(ExtractedCode(
                        code=code,
                        language=lang,
                        relevance_score=0.5
                    ))

        return extracted

    def _detect_language(self, code: str) -> Optional[str]:
        """检测代码语言"""
        scores: Dict[str, float] = {}

        for lang, pattern in self.language_patterns.items():
            matches = len(pattern.findall(code))
            if matches > 0:
                scores[lang] = matches

        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return None

    def _calculate_relevance(self, code: str, lang: str) -> float:
        """计算代码相关性"""
        length_score = min(len(code) / 500, 1.0)
        lang_score = 1.0 if lang else 0.5
        return (length_score + lang_score) / 2


# ============================================================
# 第四部分：概念提取器
# ============================================================

class ConceptExtractor:
    """关键概念提取器"""

    TECH_PATTERNS = [
        r'\b(Python|JavaScript|TypeScript|Java|C\+\+|Go|Rust|Ruby|Perl|PHP)\b',
        r'\b(API|REST|GraphQL|gRPC|WebSocket)\b',
        r'\b(Docker|Kubernetes|Container|Microservice|Serverless)\b',
        r'\b(Git|GitHub|GitLab|SVN|Version Control)\b',
        r'\b(Database|SQL|NoSQL|MongoDB|Redis|Elasticsearch)\b',
        r'\b(ML|Machine Learning|Deep Learning|Neural Network|TensorFlow|PyTorch)\b',
        r'\b(Cloud|AWS|Azure|GCP|Kubernetes|Terraform)\b',
        r'\b(Agile|Scrum|Kanban|DevOps|CI/CD)\b',
        r'\b(React|Vue|Angular|Django|Flask|Spring|Rails|Laravel)\b',
    ]

    def __init__(self):
        self.pattern = re.compile('|'.join(self.TECH_PATTERNS), re.IGNORECASE)
        print("[ConceptExtractor] 初始化概念提取器")

    def extract(self, content: str) -> List[str]:
        """提取关键概念"""
        matches = self.pattern.findall(content)
        return list(set(matches))

    def extract_from_url(self, url: str) -> List[str]:
        """从URL提取概念"""
        concepts = []
        url_lower = url.lower()

        tech_keywords = [
            'python', 'javascript', 'java', 'golang', 'rust',
            'react', 'vue', 'angular', 'django', 'flask',
            'docker', 'kubernetes', 'aws', 'tensorflow', 'pytorch',
            'api', 'database', 'git', 'linux', 'database'
        ]

        for keyword in tech_keywords:
            if keyword in url_lower:
                concepts.append(keyword)

        return concepts


# ============================================================
# 第五部分：链接分析器
# ============================================================

class LinkAnalyzer:
    """链接分析器"""

    LINK_CATEGORIES = {
        'documentation': [r'docs\.', r'documentation', r'/doc/', r'/api/', r'reference'],
        'tutorial': [r'tutorial', r'guide', r'how-to', r'getting-started', r'/blog/'],
        'github': [r'github\.com', r'raw\.githubusercontent', r'/blob/'],
        'stackoverflow': [r'stackoverflow\.com', r'/questions/', r'/tags/'],
        'video': [r'youtube\.com', r'bilibili\.com', r'vimeo\.com', r'/watch/'],
        'paper': [r'arxiv\.org', r'/pdf/', r'paper', r'/acl/', r'/neurips/'],
        'mirror': [r'fastgit', r'cnpmjs', r'mirror', r'proxy'],
    }

    def __init__(self):
        self.category_patterns = {
            cat: re.compile('|'.join(patterns), re.IGNORECASE)
            for cat, patterns in self.LINK_CATEGORIES.items()
        }
        print("[LinkAnalyzer] 初始化链接分析器")

    def extract_links(self, content: str, base_url: str = "") -> Dict[str, List[str]]:
        """提取并分类链接"""
        url_pattern = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')
        urls = url_pattern.findall(content)

        categorized: Dict[str, List[str]] = {
            'documentation': [], 'tutorial': [], 'github': [],
            'stackoverflow': [], 'video': [], 'paper': [], 'other': []
        }

        for url in urls:
            categorized_flag = False
            for cat, pattern in self.category_patterns.items():
                if pattern.search(url):
                    categorized[cat].append(url)
                    categorized_flag = True
                    break
            if not categorized_flag:
                categorized['other'].append(url)

        return categorized

    def suggest_related(self, url: str, max_count: int = 5) -> List[str]:
        """建议相关链接"""
        related = []

        if 'github.com' in url:
            parts = url.split('/')
            if len(parts) >= 5:
                related.append(f"https://github.com/{parts[3]}/{parts[4]}/issues")
                related.append(f"https://github.com/{parts[3]}/{parts[4]}/pulls")

        return related[:max_count]


# ============================================================
# 第六部分：主增强引擎
# ============================================================

class AI_ContentEnhancer:
    """AI驱动的主动内容增强引擎"""

    def __init__(self):
        self.privacy_cleaner = PrivacyCleaner()
        self.code_extractor = CodeExtractor()
        self.concept_extractor = ConceptExtractor()
        self.link_analyzer = LinkAnalyzer()

        self.enabled_enhancements = {
            EnhancementType.SUMMARY: True,
            EnhancementType.TRANSLATION: True,
            EnhancementType.CODE_EXTRACTION: True,
            EnhancementType.KEY_CONCEPTS: True,
            EnhancementType.RELATED_LINKS: True,
            EnhancementType.PRIVACY_CLEAN: True,
            EnhancementType.KNOWLEDGE_GRAPH: True,
        }

        self._knowledge_graph: Dict[str, List[str]] = {}
        print("[AI_ContentEnhancer] 初始化内容增强引擎")

    def enhance(self, content: str, url: str = "",
                content_type: ContentType = ContentType.PLAIN_TEXT,
                enhancement_types: Optional[List[EnhancementType]] = None) -> ContentEnhancement:
        """增强内容"""
        if enhancement_types is None:
            enhancement_types = [e for e, enabled in self.enabled_enhancements.items() if enabled]

        result = ContentEnhancement(
            original_content=content,
            enhanced_content=content,
            content_type=content_type
        )

        if EnhancementType.PRIVACY_CLEAN in enhancement_types:
            content = self.privacy_cleaner.clean_content(content)
            url = self.privacy_cleaner.clean_url(url)
            result.privacy_cleaned = True
            result.enhancements_applied.append(EnhancementType.PRIVACY_CLEAN)

        if EnhancementType.CODE_EXTRACTION in enhancement_types:
            result.extracted_code = self.code_extractor.extract(content)
            if result.extracted_code:
                result.enhancements_applied.append(EnhancementType.CODE_EXTRACTION)

        if EnhancementType.KEY_CONCEPTS in enhancement_types:
            concepts = self.concept_extractor.extract(content)
            if url:
                concepts.extend(self.concept_extractor.extract_from_url(url))
            result.key_concepts = list(set(concepts))
            if result.key_concepts:
                result.enhancements_applied.append(EnhancementType.KEY_CONCEPTS)
            self._update_knowledge_graph(result.key_concepts)

        if EnhancementType.RELATED_LINKS in enhancement_types:
            categorized_links = self.link_analyzer.extract_links(content, url)
            all_links = []
            for links in categorized_links.values():
                all_links.extend(links)
            result.related_links = all_links[:10]
            if result.related_links:
                result.enhancements_applied.append(EnhancementType.RELATED_LINKS)

        if EnhancementType.SUMMARY in enhancement_types:
            result.summary = self._generate_summary(content)
            if result.summary:
                result.enhancements_applied.append(EnhancementType.SUMMARY)

        result.enhanced_content = content
        result.metadata = {
            "original_length": len(result.original_content),
            "enhanced_length": len(result.enhanced_content)
        }

        return result

    def _generate_summary(self, content: str, max_length: int = 200) -> str:
        """生成摘要（简化版）"""
        clean = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
        clean = re.sub(r'`[^`]+`', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()

        if len(clean) <= max_length:
            return clean

        sentences = clean.split('。')
        summary = ""
        for sentence in sentences:
            if len(summary) + len(sentence) + 1 <= max_length:
                summary += sentence + "。"
            else:
                break

        return summary or clean[:max_length] + "..."

    def _update_knowledge_graph(self, concepts: List[str]):
        """更新知识图谱"""
        for concept in concepts:
            for other in concepts:
                if concept != other:
                    if concept not in self._knowledge_graph:
                        self._knowledge_graph[concept] = []
                    if other not in self._knowledge_graph[concept]:
                        self._knowledge_graph[concept].append(other)

    def get_related_concepts(self, concept: str) -> List[str]:
        """获取相关概念"""
        return self._knowledge_graph.get(concept, [])

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "knowledge_concepts": len(self._knowledge_graph),
            "enabled_enhancements": sum(1 for v in self.enabled_enhancements.values() if v)
        }


# ============================================================
# 第七部分：工厂函数
# ============================================================

_content_enhancer_instance: Optional[AI_ContentEnhancer] = None
_enhancer_lock = threading.Lock()


def get_content_enhancer() -> AI_ContentEnhancer:
    """获取内容增强器单例"""
    global _content_enhancer_instance

    if _content_enhancer_instance is None:
        with _enhancer_lock:
            if _content_enhancer_instance is None:
                _content_enhancer_instance = AI_ContentEnhancer()

    return _content_enhancer_instance


# ============================================================
# 第八部分：使用示例
# ============================================================

def example_usage():
    """使用示例"""

    print("=" * 60)
    print("AI 内容增强系统示例")
    print("=" * 60)

    enhancer = get_content_enhancer()

    sample_content = """
    # Python Django REST Framework 教程

    本教程介绍如何使用 Django REST Framework 构建 Web API。

    ```python
    from django.urls import path
    from rest_framework.routers import DefaultRouter

    router = DefaultRouter()
    router.register(r'users', UserViewSet)
    ```

    关键技术：
    - Python 3.8+
    - Django REST Framework
    - Docker
    - PostgreSQL
    - API REST

    相关链接：
    - https://www.django-rest-framework.org/docs/
    - https://github.com/tomchristie/django-rest-framework
    """

    print("\n1. 内容增强:")
    result = enhancer.enhance(sample_content, "https://github.com/example/django-tutorial")

    print(f"  原始长度: {result.metadata['original_length']}")
    print(f"  隐私已清理: {result.privacy_cleaned}")

    print(f"\n2. 应用了 {len(result.enhancements_applied)} 种增强:")
    for e in result.enhancements_applied:
        print(f"    - {e.value}")

    print(f"\n3. 提取的概念 ({len(result.key_concepts)}):")
    for concept in result.key_concepts[:5]:
        print(f"    - {concept}")

    print(f"\n4. 提取的代码片段 ({len(result.extracted_code)}):")
    for code in result.extracted_code:
        print(f"    - {code.language}: {len(code.code)} 字符")

    print(f"\n5. 摘要:")
    print(f"    {result.summary[:100]}...")

    print("\n6. 隐私清理:")
    test_url = "https://example.com/page?utm_source=test&fbclid=abc123&q=search"
    cleaned = enhancer.privacy_cleaner.clean_url(test_url)
    print(f"    原始: {test_url}")
    print(f"    清理后: {cleaned}")


if __name__ == "__main__":
    example_usage()