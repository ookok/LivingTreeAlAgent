"""
Translation - 翻译核心模块

参考架构: 客户端离线初翻 + 云端择优精翻

主要组件:
- models: 数据模型 (TranslatorType/Language/TranslationTask等)
- offline_translator: 离线翻译 (Argos/EasyNMT/Helsinki-NLP)
- online_translator: 在线翻译 (DeepTranslator/LibreTranslate)
- smart_translator: 智能分层翻译 (离线优先 + 在线兜底)
- translation_hub: 核心调度器 (缓存/历史/统计/搜索集成)

使用方式:
    from core.translation import get_translation_hub

    hub = get_translation_hub()

    # 单条翻译
    result = hub.translate("Hello world", target_lang="zh")
    logger.info(result.translated)

    # 批量翻译
    results = hub.translate_batch(["Hello", "World"], target_lang="zh")

    # 搜索结果翻译
    search_results = [{"title": "Apple", "text": "Apple Inc. is..."}]
    translated = hub.translate_search_results(search_results, text_field="text")
"""

from .models import (
    # 枚举
    TranslatorType,
    TranslatorStatus,
    Language,
    # 数据模型
    TranslationTask,
    TranslationResult,
    BatchTranslationResult,
    TranslatorInfo,
    # 常量
    LANGUAGE_NAMES,
    LANGUAGE_ALIASES,
    SUPPORTED_PAIRS_OFFLINE,
    BATCH_SIZE_THRESHOLD,
    MAX_OFFLINE_CHUNK,
    # 函数
    normalize_language,
)

from .offline_translator import OfflineTranslator, get_offline_translator
from .online_translator import OnlineTranslator, get_online_translator
from .smart_translator import SmartTranslator, get_smart_translator, SmartTranslateConfig
from .translation_hub import TranslationHub, get_translation_hub, CacheEntry
from core.logger import get_logger
logger = get_logger('translation.__init__')


__all__ = [
    # 枚举
    "TranslatorType",
    "TranslatorStatus",
    "Language",
    # 数据模型
    "TranslationTask",
    "TranslationResult",
    "BatchTranslationResult",
    "TranslatorInfo",
    "CacheEntry",
    "SmartTranslateConfig",
    # 常量
    "LANGUAGE_NAMES",
    "LANGUAGE_ALIASES",
    "SUPPORTED_PAIRS_OFFLINE",
    "BATCH_SIZE_THRESHOLD",
    "MAX_OFFLINE_CHUNK",
    # 函数
    "normalize_language",
    # 翻译器
    "OfflineTranslator",
    "get_offline_translator",
    "OnlineTranslator",
    "get_online_translator",
    "SmartTranslator",
    "get_smart_translator",
    # 核心
    "TranslationHub",
    "get_translation_hub",
]
