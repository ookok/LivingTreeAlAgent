"""
离线翻译器 - Offline Translator
支持: Argos Translate / EasyNMT / Helsinki-NLP

特点:
- 纯本地运行, 无需网络
- 适合短文本快速翻译
- 隐私优先
"""

import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass

from .models import (
    TranslatorType, TranslatorStatus, TranslatorInfo,
    TranslationTask, TranslationResult,
    normalize_language, SUPPORTED_PAIRS_OFFLINE, MAX_OFFLINE_CHUNK
)


class OfflineTranslator:
    """
    离线翻译器基类

    设计思路:
    1. 延迟加载模型 (按需加载)
    2. 支持多种后端 (Argos/EasyNMT/Helsinki)
    3. 自动选择最优后端
    """

    def __init__(self, model_dir: Optional[str] = None):
        """
        Args:
            model_dir: 模型存储目录, 默认 ~/.hermes-desktop/translation_models/
        """
        if model_dir is None:
            model_dir = str(Path.home() / ".hermes-desktop" / "translation_models")

        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # 实际翻译器
        self._translator = None
        self._translator_type: Optional[TranslatorType] = None
        self._status = TranslatorStatus.UNKNOWN
        self._error = ""

        # 可用后端
        self._available_backends: List[TranslatorType] = []

        # 检测可用后端
        self._detect_available_backends()

    def _detect_available_backends(self):
        """检测可用的离线翻译后端"""
        self._available_backends = []

        # 检测 Argos Translate
        try:
            import argostranslate
            self._available_backends.append(TranslatorType.ARGOS)
        except ImportError:
            pass

        # 检测 EasyNMT
        try:
            from easynmt import EasyNMT
            self._available_backends.append(TranslatorType.EASY_NMT)
        except ImportError:
            pass

        # 检测 Helsinki-NLP (transformers)
        try:
            from transformers import pipeline
            self._available_backends.append(TranslatorType.HELSINKI)
        except ImportError:
            pass

    def get_available_translators(self) -> List[TranslatorInfo]:
        """获取可用的翻译器列表"""
        infos = []

        if TranslatorType.ARGOS in self._available_backends:
            infos.append(TranslatorInfo(
                name="Argos Translate",
                type=TranslatorType.ARGOS,
                status=TranslatorStatus.AVAILABLE if self._translator_type != TranslatorType.ARGOS else self._status,
                languages=["en", "zh-CN", "zh-TW", "ja", "ko", "fr", "de", "es", "ru", "ar", "pt", "vi", "th"],
                is_offline=True,
                model_size="~200MB"
            ))

        if TranslatorType.EASY_NMT in self._available_backends:
            infos.append(TranslatorInfo(
                name="EasyNMT (OPUS-MT)",
                type=TranslatorType.EASY_NMT,
                status=TranslatorStatus.AVAILABLE if self._translator_type != TranslatorType.EASY_NMT else self._status,
                languages=["en", "zh-CN", "ja", "ko", "de", "fr", "es", "ru"],
                is_offline=True,
                model_size="~500MB"
            ))

        if TranslatorType.HELSINKI in self._available_backends:
            infos.append(TranslatorInfo(
                name="Helsinki-NLP",
                type=TranslatorType.HELSINKI,
                status=TranslatorStatus.AVAILABLE if self._translator_type != TranslatorType.HELSINKI else self._status,
                languages=["en", "zh-CN", "fi", "sv", "ru", "de", "fr"],
                is_offline=True,
                model_size="~350MB"
            ))

        return infos

    def _load_translator(self, translator_type: TranslatorType):
        """加载翻译器"""
        if self._translator_type == translator_type and self._translator is not None:
            return

        self._status = TranslatorStatus.LOADING
        self._error = ""

        try:
            if translator_type == TranslatorType.ARGOS:
                self._load_argos()
            elif translator_type == TranslatorType.EASY_NMT:
                self._load_easynmt()
            elif translator_type == TranslatorType.HELSINKI:
                self._load_helsinki()
            else:
                raise ValueError(f"Unsupported translator type: {translator_type}")

            self._translator_type = translator_type
            self._status = TranslatorStatus.AVAILABLE

        except Exception as e:
            self._status = TranslatorStatus.ERROR
            self._error = str(e)
            raise

    def _load_argos(self):
        """加载 Argos Translate"""
        import argostranslate
        import argostranslate.package
        import argostranslate.translate

        # 更新包索引
        try:
            argostranslate.package.update_package_index()
        except Exception:
            pass  # 离线模式可能无法更新

        self._translator = {
            "package": argostranslate.package,
            "translate": argostranslate.translate
        }

    def _load_easynmt(self):
        """加载 EasyNMT"""
        from easynmt import EasyNMT

        # 使用 opus-mt 模型 (轻量)
        model_path = self.model_dir / "easynmt_opus_mt"
        if model_path.exists():
            self._translator = EasyNMT("opus-mt", model_path=str(model_path))
        else:
            self._translator = EasyNMT("opus-mt")

    def _load_helsinki(self):
        """加载 Helsinki-NLP"""
        from transformers import pipeline
        import os
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

        # 使用 opus-mt-en-zh 模型
        self._translator = pipeline(
            "translation_en_to_zh",
            model="Helsinki-NLP/opus-mt-en-zh",
            cache_dir=str(self.model_dir / "helsinki")
        )

    def translate(self,
                  text: str,
                  source_lang: str = "auto",
                  target_lang: str = "zh",
                  translator_type: TranslatorType = TranslatorType.ARGOS) -> TranslationResult:
        """
        翻译单条文本

        Args:
            text: 原文
            source_lang: 源语言
            target_lang: 目标语言
            translator_type: 翻译器类型

        Returns:
            TranslationResult 对象
        """
        start_time = time.time()

        # 规范化语言代码
        source_lang = normalize_language(source_lang)
        target_lang = normalize_language(target_lang)

        # 检查是否支持该语言对
        pair_key = (source_lang if source_lang != "auto" else "en", target_lang)
        if pair_key not in SUPPORTED_PAIRS_OFFLINE and source_lang != "auto":
            # 不支持的组合, 尝试用在线翻译
            raise ValueError(f"Unsupported language pair for offline: {source_lang} -> {target_lang}")

        # 加载翻译器
        if self._translator_type != translator_type or self._translator is None:
            self._load_translator(translator_type)

        self._status = TranslatorStatus.TRANSLATING

        try:
            if translator_type == TranslatorType.ARGOS:
                translated = self._translate_argos(text, source_lang, target_lang)
            elif translator_type == TranslatorType.EASY_NMT:
                translated = self._translate_easynmt(text, source_lang, target_lang)
            elif translator_type == TranslatorType.HELSINKI:
                translated = self._translate_helsinki(text)
            else:
                raise ValueError(f"Unsupported translator type: {translator_type}")

            self._status = TranslatorStatus.AVAILABLE

            return TranslationResult(
                original=text,
                translated=translated,
                source_lang=source_lang,
                target_lang=target_lang,
                translator=translator_type,
                confidence=0.9  # 离线翻译默认置信度
            )

        except Exception as e:
            self._status = TranslatorStatus.ERROR
            self._error = str(e)
            raise

    def _translate_argos(self, text: str, source_lang: str, target_lang: str) -> str:
        """使用 Argos Translate 翻译"""
        trans = self._translator["translate"]

        # 安装语言包 (如果需要)
        try:
            from_arg = source_lang if source_lang != "auto" else "en"
            to_arg = target_lang

            # 获取已安装的包
            installed_packages = trans.get_installed_languages()
            package_map = {lang.code: lang for lang in installed_packages}

            # 查找语言对
            from_lang = package_map.get(from_arg)
            to_lang = package_map.get(to_arg)

            if from_lang and to_lang:
                return trans.translate(text, from_lang, to_lang)
            else:
                # 尝试自动安装
                return trans.translate(text, from_lang or package_map.get("en"), to_lang)

        except Exception as e:
            raise RuntimeError(f"Argos translation failed: {e}")

    def _translate_easynmt(self, text: str, source_lang: str, target_lang: str) -> str:
        """使用 EasyNMT 翻译"""
        try:
            if source_lang == "auto":
                return self._translator.translate(text, target_lang=target_lang)
            else:
                return self._translator.translate(text, source_lang=source_lang, target_lang=target_lang)
        except Exception as e:
            raise RuntimeError(f"EasyNMT translation failed: {e}")

    def _translate_helsinki(self, text: str) -> str:
        """使用 Helsinki-NLP 翻译"""
        try:
            result = self._translator(text)
            return result[0]["translation_text"]
        except Exception as e:
            raise RuntimeError(f"Helsinki translation failed: {e}")

    def translate_batch(self,
                       texts: List[str],
                       source_lang: str = "auto",
                       target_lang: str = "zh",
                       translator_type: TranslatorType = TranslatorType.ARGOS,
                       progress_callback: Optional[Callable] = None) -> List[TranslationResult]:
        """
        批量翻译

        Args:
            texts: 文本列表
            source_lang: 源语言
            target_lang: 目标语言
            translator_type: 翻译器类型
            progress_callback: 进度回调 (progress: float)

        Returns:
            TranslationResult 列表
        """
        results = []

        for i, text in enumerate(texts):
            try:
                result = self.translate(text, source_lang, target_lang, translator_type)
                results.append(result)
            except Exception as e:
                results.append(TranslationResult(
                    original=text,
                    translated="",
                    source_lang=source_lang,
                    target_lang=target_lang,
                    translator=translator_type,
                    confidence=0
                ))

            if progress_callback:
                progress_callback((i + 1) / len(texts))

        return results

    def get_status(self) -> TranslatorStatus:
        """获取状态"""
        return self._status

    def get_error(self) -> str:
        """获取错误信息"""
        return self._error

    def is_available(self) -> bool:
        """检查是否可用"""
        return len(self._available_backends) > 0

    def close(self):
        """关闭翻译器, 释放资源"""
        self._translator = None
        self._translator_type = None
        self._status = TranslatorStatus.UNKNOWN


# 单例
_offline_translator: Optional[OfflineTranslator] = None


def get_offline_translator() -> OfflineTranslator:
    """获取离线翻译器单例"""
    global _offline_translator
    if _offline_translator is None:
        _offline_translator = OfflineTranslator()
    return _offline_translator
