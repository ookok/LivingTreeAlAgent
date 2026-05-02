"""
星图导航仪 (Star Navigator)

目标：接受模糊输入（文字/博客/URL），输出明确需求。

支持输入：
- 文字描述："能解析 PDF 表格的 Python 库"
- 博客链接：Agent-Reach 抓取内容
- 直接仓库 URL（跳过发现）

AI 解析：提取 {功能, 语言, 形式(cli/lib), 约束}
输出：结构化需求单（供下一阶段匹配）
"""

import re
import json
from dataclasses import dataclass, field
from typing import Optional, Literal
from enum import Enum


class InputType(Enum):
    """输入类型"""
    TEXT = "text"           # 文字描述
    URL = "url"             # 博客/仓库URL
    REPO_URL = "repo_url"   # 直接仓库URL（跳过发现）


class Language(Enum):
    """编程语言"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CSHARP = "csharp"
    CPP = "cpp"
    RUBY = "ruby"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    UNKNOWN = "unknown"


class PackageForm(Enum):
    """包形式"""
    LIB = "lib"             # 库/SDK
    CLI = "cli"             # 命令行工具
    FRAMEWORK = "framework" # 框架
    LIB_CLI = "lib,cli"     # 两者都有


@dataclass
class RequirementSpec:
    """需求规格单"""
    raw_input: str                      # 原始输入
    input_type: InputType               # 输入类型
    intent: str = ""                    # 功能意图

    # 解析出的字段
    features: list[str] = field(default_factory=list)  # 功能关键词
    languages: list[Language] = field(default_factory=list)  # 语言
    form: PackageForm = PackageForm.LIB # 包形式
    constraints: list[str] = field(default_factory=list)  # 约束条件

    # 可选：直接指定的仓库
    direct_repo: Optional[str] = None   # 直接仓库URL

    # AI理解的其他需求
    use_case: str = ""                  # 使用场景
    environment: str = ""               # 运行环境

    def to_dict(self) -> dict:
        return {
            "raw_input": self.raw_input,
            "input_type": self.input_type.value,
            "intent": self.intent,
            "features": self.features,
            "languages": [l.value for l in self.languages],
            "form": self.form.value,
            "constraints": self.constraints,
            "direct_repo": self.direct_repo,
            "use_case": self.use_case,
            "environment": self.environment,
        }


class StarNavigator:
    """星图导航仪 - 需求输入解析"""

    # 功能关键词映射
    FEATURE_PATTERNS = {
        'pdf': ['pdf', '解析pdf', 'pdf解析', 'pdf提取', 'pdf转文本'],
        'excel': ['excel', 'xlsx', 'csv', '电子表格', '表格解析'],
        'image': ['图片', '图像', 'ocr', '图片识别', '图像处理'],
        'video': ['视频', '视频处理', 'ffmpeg', '视频编解码'],
        'audio': ['音频', '语音', 'tts', 'asr', '语音合成', '语音识别'],
        'nlp': ['nlp', '自然语言', '文本分析', '情感分析', '分词'],
        'web_scraping': ['爬虫', '网页抓取', 'web scraping', 'scraper'],
        'database': ['数据库', 'db', 'sql', 'orm', '数据存储'],
        'api': ['api', '接口', 'rest', 'graphql', '网络请求'],
        'crypto': ['加密', 'crypto', 'hash', '签名'],
        'ml': ['机器学习', 'ml', '模型', 'train', '训练'],
        'inference': ['推理', 'inference', 'inference', '部署模型'],
        'compress': ['压缩', 'zip', 'tar', '解压缩'],
        'async': ['异步', 'async', '并发', 'parallel'],
        'json': ['json', '序列化', 'yaml', 'toml', '配置文件'],
        'auth': ['认证', 'auth', 'oauth', 'jwt', '登录'],
        'websocket': ['websocket', '实时', 'socket', '通信'],
    }

    # 语言检测关键词
    LANGUAGE_PATTERNS = {
        Language.PYTHON: ['python', 'pip', 'pypi', 'py'],
        Language.JAVASCRIPT: ['javascript', 'js', 'node', 'npm', 'nodejs'],
        Language.TYPESCRIPT: ['typescript', 'ts', 'd.ts'],
        Language.GO: ['go', 'golang', 'goproxy'],
        Language.RUST: ['rust', 'cargo', 'crates.io'],
        Language.JAVA: ['java', 'maven', 'gradle', 'jar'],
        Language.CSHARP: ['csharp', 'c#', '.net', 'nuget'],
        Language.CPP: ['c++', 'cpp', 'cmake'],
        Language.RUBY: ['ruby', 'gem', 'rubygems'],
        Language.SWIFT: ['swift', 'cocoapods', 'spm'],
        Language.KOTLIN: ['kotlin', 'kt', 'gradle'],
    }

    # 约束关键词
    CONSTRAINT_PATTERNS = {
        'offline': ['离线', '本地', 'offline', 'local', '不联网'],
        'free': ['免费', 'free', '开源', 'open source', 'mit', 'apache'],
        'no_gpl': ['不lgpl', '不 GPL', '避免 GPL', 'non-gpl'],
        'lightweight': ['轻量', '轻量级', 'lightweight', 'small', 'fast'],
        'production': ['生产', '生产级', 'production', 'stable', '成熟'],
        'recent': ['最新', '最近', 'recent', 'updated', '活跃'],
    }

    def __init__(self):
        self._cache: dict[str, RequirementSpec] = {}

    def parse(self, user_input: str) -> RequirementSpec:
        """
        解析用户输入为结构化需求单

        Args:
            user_input: 用户输入（文字描述/URL/仓库URL）

        Returns:
            RequirementSpec: 结构化需求规格
        """
        # 检查缓存
        cache_key = user_input.strip().lower()
        if cache_key in self._cache:
            return self._cache[cache_key]

        spec = RequirementSpec(
            raw_input=user_input,
            input_type=self._detect_input_type(user_input)
        )

        # 根据输入类型处理
        if spec.input_type == InputType.REPO_URL:
            spec.direct_repo = user_input.strip()
            spec.intent = "直接指定仓库"
        else:
            # 解析文字内容
            self._parse_text_content(spec, user_input)

        # 缓存结果
        self._cache[cache_key] = spec
        return spec

    def _detect_input_type(self, user_input: str) -> InputType:
        """检测输入类型"""
        user_input = user_input.strip().lower()

        # GitHub/Gitee 直接仓库
        if any(domain in user_input for domain in ['github.com/', 'gitee.com/', 'gitlab.com/']):
            if any(suffix in user_input for suffix in ['/releases', '/tags', '/tree/', '.git']):
                return InputType.REPO_URL
            return InputType.URL

        # 普通URL
        if user_input.startswith(('http://', 'https://', 'www.')):
            return InputType.URL

        return InputType.TEXT

    def _parse_text_content(self, spec: RequirementSpec, text: str):
        """解析文字内容"""
        text_lower = text.lower()

        # 提取功能
        spec.features = self._extract_features(text_lower)

        # 提取语言
        spec.languages = self._extract_languages(text_lower)
        if not spec.languages:
            spec.languages = [Language.UNKNOWN]  # 默认未知

        # 提取形式
        spec.form = self._extract_form(text_lower)

        # 提取约束
        spec.constraints = self._extract_constraints(text_lower)

        # 生成意图摘要
        spec.intent = self._generate_intent(spec)

    def _extract_features(self, text: str) -> list[str]:
        """提取功能关键词"""
        features = []
        for feature, patterns in self.FEATURE_PATTERNS.items():
            if any(p in text for p in patterns):
                features.append(feature)
        return features if features else ['general']  # 默认通用

    def _extract_languages(self, text: str) -> list[Language]:
        """提取编程语言"""
        languages = []
        for lang, patterns in self.LANGUAGE_PATTERNS.items():
            if any(p in text for p in patterns):
                languages.append(lang)
        return languages

    def _extract_form(self, text: str) -> PackageForm:
        """提取包形式"""
        if any(k in text for k in ['命令行', 'cli tool', 'command line', '终端', 'shell']):
            return PackageForm.CLI
        if any(k in text for k in ['框架', 'framework', 'mvc', 'orm']):
            return PackageForm.FRAMEWORK
        return PackageForm.LIB

    def _extract_constraints(self, text: str) -> list[str]:
        """提取约束条件"""
        constraints = []
        for constraint, patterns in self.CONSTRAINT_PATTERNS.items():
            if any(p in text for p in patterns):
                constraints.append(constraint)
        return constraints

    def _generate_intent(self, spec: RequirementSpec) -> str:
        """生成意图摘要"""
        parts = []

        # 功能
        if spec.features:
            parts.append(f"功能: {', '.join(spec.features)}")

        # 语言
        if spec.languages and spec.languages[0] != Language.UNKNOWN:
            lang_names = [l.value for l in spec.languages]
            parts.append(f"语言: {', '.join(lang_names)}")

        # 形式
        parts.append(f"形式: {spec.form.value}")

        # 约束
        if spec.constraints:
            parts.append(f"约束: {', '.join(spec.constraints)}")

        return " | ".join(parts)

    def spec_to_query(self, spec: RequirementSpec) -> str:
        """
        将需求规格转换为搜索查询

        Args:
            spec: 需求规格

        Returns:
            str: 搜索查询字符串
        """
        if spec.direct_repo:
            return spec.direct_repo

        query_parts = []

        # 功能
        if spec.features:
            query_parts.append(' '.join(spec.features))

        # 语言
        if spec.languages:
            for lang in spec.languages:
                if lang != Language.UNKNOWN:
                    query_parts.append(lang.value)
                    break

        # 形式
        query_parts.append(spec.form.value)

        return ' '.join(query_parts)

    def format_spec_display(self, spec: RequirementSpec) -> str:
        """格式化需求规格为显示文本"""
        lines = [
            f"📥 原始输入: {spec.raw_input}",
            f"🎯 输入类型: {spec.input_type.value}",
            f"💡 意图: {spec.intent or '未识别'}",
        ]

        if spec.features:
            lines.append(f"⚙️ 功能: {', '.join(spec.features)}")

        if spec.languages:
            lang_names = [l.value for l in spec.languages]
            lines.append(f"🔧 语言: {', '.join(lang_names)}")

        lines.append(f"📦 形式: {spec.form.value}")

        if spec.constraints:
            lines.append(f"⏸️ 约束: {', '.join(spec.constraints)}")

        if spec.direct_repo:
            lines.append(f"🔗 直接仓库: {spec.direct_repo}")

        return '\n'.join(lines)