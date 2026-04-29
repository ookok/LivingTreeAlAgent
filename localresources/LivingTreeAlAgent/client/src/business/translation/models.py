"""
翻译核心数据模型 - Translation Core Models

支持:
- 离线翻译: Argos Translate / EasyNMT / Helsinki-NLP
- 在线翻译: DeepTranslator / LibreTranslate
- 智能分层: 离线优先 + 在线兜底
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


class TranslatorType(str, Enum):
    """翻译器类型"""
    # 离线翻译器
    ARGOS = "argos"           # Argos Translate (LibreTranslate引擎)
    EASY_NMT = "easynmt"     # EasyNMT (OPUS-MT)
    HELSINKI = "helsinki"     # Helsinki-NLP (transformers)

    # 在线翻译器
    DEEP_TRANSLATOR = "deep_translator"  # DeepTranslator (聚合)
    LIBRE_TRANSLATE = "libretranslate"   # LibreTranslate API

    # 智能分层
    SMART = "smart"           # 智能分层 (离线优先 + 在线兜底)


class TranslatorStatus(str, Enum):
    """翻译器状态"""
    UNKNOWN = "unknown"
    AVAILABLE = "available"   # 可用
    LOADING = "loading"       # 加载中
    TRANSLATING = "translating"  # 翻译中
    ERROR = "error"          # 错误
    OFFLINE = "offline"      # 离线


class Language(str, Enum):
    """支持的语言"""
    AUTO = "auto"             # 自动检测
    ZH = "zh"                 # 中文
    ZH_CN = "zh-CN"           # 简体中文
    ZH_TW = "zh-TW"           # 繁体中文
    EN = "en"                 # 英语
    JA = "ja"                 # 日语
    KO = "ko"                 # 韩语
    FR = "fr"                 # 法语
    DE = "de"                 # 德语
    ES = "es"                 # 西班牙语
    RU = "ru"                 # 俄语
    AR = "ar"                 # 阿拉伯语
    PT = "pt"                 # 葡萄牙语
    IT = "it"                 # 意大利语
    VI = "vi"                 # 越南语
    TH = "th"                 # 泰语
    UK = "uk"                 # 乌克兰语


# 语言名称映射
LANGUAGE_NAMES = {
    "auto": "自动检测",
    "zh": "中文",
    "zh-CN": "简体中文",
    "zh-TW": "繁体中文",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
    "fr": "法语",
    "de": "德语",
    "es": "西班牙语",
    "ru": "俄语",
    "ar": "阿拉伯语",
    "pt": "葡萄牙语",
    "it": "意大利语",
    "vi": "越南语",
    "th": "泰语",
    "uk": "乌克兰语",
}

# 语言代码别名 (兼容不同格式)
LANGUAGE_ALIASES = {
    "zh-cn": "zh-CN",
    "zh-tw": "zh-TW",
    "chinese": "zh-CN",
    "english": "en",
    "japanese": "ja",
    "korean": "ko",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "russian": "ru",
    "arabic": "ar",
}


def normalize_language(lang: str) -> str:
    """规范化语言代码"""
    lang = lang.lower().strip()
    return LANGUAGE_ALIASES.get(lang, lang)


@dataclass
class TranslationTask:
    """翻译任务"""
    task_id: str = ""
    text: str = ""            # 原始文本
    source_lang: str = "auto" # 源语言
    target_lang: str = "zh"   # 目标语言
    translator_type: TranslatorType = TranslatorType.SMART

    # 结果
    translated_text: str = ""  # 翻译后文本
    status: TranslatorStatus = TranslatorStatus.UNKNOWN
    error: str = ""

    # 元数据
    char_count: int = 0      # 字符数
    created_at: float = 0     # 创建时间
    completed_at: float = 0   # 完成时间
    latency_ms: float = 0     # 延迟 (毫秒)

    def get_duration_ms(self) -> float:
        """获取翻译耗时"""
        if self.completed_at > 0 and self.created_at > 0:
            return (self.completed_at - self.created_at) * 1000
        return self.latency_ms


@dataclass
class TranslationResult:
    """翻译结果"""
    original: str              # 原文
    translated: str           # 译文
    source_lang: str          # 源语言
    target_lang: str          # 目标语言
    translator: TranslatorType  # 使用的翻译器
    confidence: float = 0     # 置信度 (0-1)
    alternatives: List[str] = field(default_factory=list)  # 备选翻译

    def get_lang_name(self, lang: str) -> str:
        """获取语言名称"""
        return LANGUAGE_NAMES.get(lang, lang)


@dataclass
class BatchTranslationResult:
    """批量翻译结果"""
    results: List[TranslationResult] = field(default_factory=list)
    total_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    total_latency_ms: float = 0

    def get_success_rate(self) -> float:
        """获取成功率"""
        if self.total_count == 0:
            return 0
        return self.success_count / self.total_count


@dataclass
class TranslatorInfo:
    """翻译器信息"""
    name: str                 # 名称
    type: TranslatorType      # 类型
    status: TranslatorStatus  # 状态
    languages: List[str] = field(default_factory=list)  # 支持的语言
    model_size: str = ""     # 模型大小 (离线)
    is_offline: bool = True  # 是否支持离线
    error: str = ""           # 错误信息

    # 性能指标
    avg_latency_ms: float = 0  # 平均延迟
    total_requests: int = 0     # 总请求数
    success_count: int = 0      # 成功次数


# 支持的语言对 (用于快速检查)
SUPPORTED_PAIRS_OFFLINE = {
    # Argos Translate 支持的主要语言对
    ("en", "zh-CN"): True,
    ("en", "zh-TW"): True,
    ("en", "ja"): True,
    ("en", "ko"): True,
    ("en", "fr"): True,
    ("en", "de"): True,
    ("en", "es"): True,
    ("en", "ru"): True,
    ("en", "ar"): True,
    ("en", "pt"): True,
    ("en", "it"): True,
    ("en", "vi"): True,
    ("en", "th"): True,
    ("zh-CN", "en"): True,
    ("zh-TW", "en"): True,
    ("ja", "en"): True,
    ("ko", "en"): True,
    ("fr", "en"): True,
    ("de", "en"): True,
    ("es", "en"): True,
    ("ru", "en"): True,
}

# 批量翻译阈值
BATCH_SIZE_THRESHOLD = 500  # 字符数阈值, 超过则用在线
MAX_OFFLINE_CHUNK = 1000    # 离线翻译最大单次字符数
