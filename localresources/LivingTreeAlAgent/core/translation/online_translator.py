"""
在线翻译器 - Online Translator
支持: DeepTranslator / LibreTranslate

特点:
- 支持更多语言对
- 适合长文本和专业术语
- 需要网络连接
"""

import time
import asyncio
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass

from .models import (
    TranslatorType, TranslatorStatus, TranslatorInfo,
    TranslationTask, TranslationResult, BatchTranslationResult,
    normalize_language, BATCH_SIZE_THRESHOLD
)


class OnlineTranslator:
    """
    在线翻译器

    支持的后端:
    1. DeepTranslator - 聚合 Google/DeepL/Microsoft 等
    2. LibreTranslate - 自建或公有实例
    """

    def __init__(self, libretranslate_url: str = ""):
        """
        Args:
            libretranslate_url: LibreTranslate API 地址 (可选)
        """
        self._libretranslate_url = libretranslate_url
        self._status = TranslatorStatus.UNKNOWN
        self._error = ""

        # DeepTranslator 实例 (延迟加载)
        self._deep_translator = None

        # LibreTranslate 实例 (延迟加载)
        self._libre_client = None

        # 检测可用后端
        self._available_backends: List[TranslatorType] = []
        self._detect_available_backends()

    def _detect_available_backends(self):
        """检测可用的在线翻译后端"""
        self._available_backends = []

        # 检测 DeepTranslator
        try:
            import deep_translator
            self._available_backends.append(TranslatorType.DEEP_TRANSLATOR)
        except ImportError:
            pass

        # 检测 LibreTranslate
        if self._libretranslate_url:
            try:
                import libretranslatepy
                self._available_backends.append(TranslatorType.LIBRE_TRANSLATE)
            except ImportError:
                pass

    def get_available_translators(self) -> List[TranslatorInfo]:
        """获取可用的翻译器列表"""
        infos = []

        if TranslatorType.DEEP_TRANSLATOR in self._available_backends:
            infos.append(TranslatorInfo(
                name="DeepTranslator (聚合)",
                type=TranslatorType.DEEP_TRANSLATOR,
                status=TranslatorStatus.AVAILABLE,
                languages=[
                    "en", "zh-CN", "zh-TW", "ja", "ko", "fr", "de", "es",
                    "ru", "ar", "pt", "it", "vi", "th", "uk"
                ],
                is_offline=False,
                model_size="N/A (API)"
            ))

        if TranslatorType.LIBRE_TRANSLATE in self._available_backends:
            infos.append(TranslatorInfo(
                name="LibreTranslate",
                type=TranslatorType.LIBRE_TRANSLATE,
                status=TranslatorStatus.AVAILABLE,
                languages=["en", "zh-CN", "ja", "ko", "fr", "de", "es", "ru", "ar"],
                is_offline=False,
                model_size=f"API: {self._libretranslate_url or '公共实例'}"
            ))

        return infos

    def _load_deep_translator(self):
        """加载 DeepTranslator"""
        if self._deep_translator is None:
            from deep_translator import GoogleTranslator
            self._deep_translator = GoogleTranslator
        return self._deep_translator

    def _load_libre_client(self):
        """加载 LibreTranslate 客户端"""
        if self._libre_client is None:
            import libretranslatepy
            if self._libretranslate_url:
                self._libre_client = libretranslatepy.LibreTranslate(self._libretranslate_url)
            else:
                self._libre_client = libretranslatepy.LibreTranslate()
        return self._libre_client

    def translate(self,
                  text: str,
                  source_lang: str = "auto",
                  target_lang: str = "zh",
                  translator_type: TranslatorType = TranslatorType.DEEP_TRANSLATOR) -> TranslationResult:
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

        self._status = TranslatorStatus.TRANSLATING

        try:
            if translator_type == TranslatorType.DEEP_TRANSLATOR:
                translated = self._translate_deep(text, source_lang, target_lang)
            elif translator_type == TranslatorType.LIBRE_TRANSLATE:
                translated = self._translate_libre(text, source_lang, target_lang)
            else:
                raise ValueError(f"Unsupported translator type: {translator_type}")

            self._status = TranslatorStatus.AVAILABLE

            return TranslationResult(
                original=text,
                translated=translated,
                source_lang=source_lang,
                target_lang=target_lang,
                translator=translator_type,
                confidence=0.95  # 在线翻译默认置信度较高
            )

        except Exception as e:
            self._status = TranslatorStatus.ERROR
            self._error = str(e)
            raise

    def _translate_deep(self, text: str, source_lang: str, target_lang: str) -> str:
        """使用 DeepTranslator 翻译"""
        GoogleTranslator = self._load_deep_translator()

        try:
            # Google Translate 不支持 auto 检测时指定目标语言
            if source_lang == "auto":
                translator = GoogleTranslator(source="auto", target=target_lang)
            else:
                translator = GoogleTranslator(source=source_lang, target=target_lang)

            return translator.translate(text)

        except Exception as e:
            raise RuntimeError(f"DeepTranslator failed: {e}")

    def _translate_libre(self, text: str, source_lang: str, target_lang: str) -> str:
        """使用 LibreTranslate 翻译"""
        client = self._load_libre_client()

        try:
            # 处理 auto 检测
            src = source_lang if source_lang != "auto" else "auto"

            result = client.translate(text, source=src, target=target_lang)
            return result.get("translatedText", "")

        except Exception as e:
            raise RuntimeError(f"LibreTranslate failed: {e}")

    async def translate_async(self,
                              text: str,
                              source_lang: str = "auto",
                              target_lang: str = "zh",
                              translator_type: TranslatorType = TranslatorType.DEEP_TRANSLATOR) -> TranslationResult:
        """异步翻译"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.translate,
            text, source_lang, target_lang, translator_type
        )

    def translate_batch(self,
                        texts: List[str],
                        source_lang: str = "auto",
                        target_lang: str = "zh",
                        translator_type: TranslatorType = TranslatorType.DEEP_TRANSLATOR,
                        progress_callback: Optional[Callable] = None) -> BatchTranslationResult:
        """
        批量翻译

        Args:
            texts: 文本列表
            source_lang: 源语言
            target_lang: 目标语言
            translator_type: 翻译器类型
            progress_callback: 进度回调

        Returns:
            BatchTranslationResult 对象
        """
        start_time = time.time()
        results = []
        success_count = 0
        failed_count = 0

        for i, text in enumerate(texts):
            try:
                result = self.translate(text, source_lang, target_lang, translator_type)
                results.append(result)
                success_count += 1
            except Exception as e:
                results.append(TranslationResult(
                    original=text,
                    translated="",
                    source_lang=source_lang,
                    target_lang=target_lang,
                    translator=translator_type,
                    confidence=0
                ))
                failed_count += 1

            if progress_callback:
                progress_callback((i + 1) / len(texts))

        total_latency = (time.time() - start_time) * 1000

        return BatchTranslationResult(
            results=results,
            total_count=len(texts),
            success_count=success_count,
            failed_count=failed_count,
            total_latency_ms=total_latency
        )

    async def translate_batch_async(self,
                                     texts: List[str],
                                     source_lang: str = "auto",
                                     target_lang: str = "zh",
                                     translator_type: TranslatorType = TranslatorType.DEEP_TRANSLATOR,
                                     max_concurrency: int = 3) -> BatchTranslationResult:
        """
        异步批量翻译 (带并发限制)

        Args:
            texts: 文本列表
            source_lang: 源语言
            target_lang: 目标语言
            translator_type: 翻译器类型
            max_concurrency: 最大并发数

        Returns:
            BatchTranslationResult 对象
        """
        start_time = time.time()
        results = []
        success_count = 0
        failed_count = 0

        # 使用信号量限制并发
        semaphore = asyncio.Semaphore(max_concurrency)

        async def translate_one(text: str):
            nonlocal success_count, failed_count
            async with semaphore:
                try:
                    result = await self.translate_async(text, source_lang, target_lang, translator_type)
                    success_count += 1
                    return result
                except Exception:
                    failed_count += 1
                    return TranslationResult(
                        original=text,
                        translated="",
                        source_lang=source_lang,
                        target_lang=target_lang,
                        translator=translator_type,
                        confidence=0
                    )

        # 并发翻译
        tasks = [translate_one(text) for text in texts]
        results = await asyncio.gather(*tasks)

        total_latency = (time.time() - start_time) * 1000

        return BatchTranslationResult(
            results=list(results),
            total_count=len(texts),
            success_count=success_count,
            failed_count=failed_count,
            total_latency_ms=total_latency
        )

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
        """关闭翻译器"""
        self._deep_translator = None
        self._libre_client = None
        self._status = TranslatorStatus.UNKNOWN


# 单例
_online_translator: Optional[OnlineTranslator] = None


def get_online_translator(libretranslate_url: str = "") -> OnlineTranslator:
    """获取在线翻译器单例"""
    global _online_translator
    if _online_translator is None:
        _online_translator = OnlineTranslator(libretranslate_url)
    return _online_translator
