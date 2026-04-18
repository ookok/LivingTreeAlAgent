"""
智能分层翻译器 - Smart Translator
策略: 客户端离线初翻 + 云端择优精翻

设计思路:
1. 短文本 (<500字符): 离线优先, 快速响应
2. 长文本 (>=500字符): 在线翻译, 质量优先
3. 离线失败: 自动切换到在线
4. 批量翻译: 并行 + 智能分块
"""

import time
import asyncio
from typing import Optional, List, Dict, Callable, Tuple
from dataclasses import dataclass

from .models import (
    TranslatorType, TranslatorStatus,
    TranslationTask, TranslationResult, BatchTranslationResult,
    normalize_language, BATCH_SIZE_THRESHOLD, MAX_OFFLINE_CHUNK
)
from .offline_translator import OfflineTranslator, get_offline_translator
from .online_translator import OnlineTranslator, get_online_translator


@dataclass
class SmartTranslateConfig:
    """智能翻译配置"""
    # 离线翻译阈值 (字符数)
    offline_threshold: int = BATCH_SIZE_THRESHOLD  # 500字符

    # 最大离线单次翻译字符数
    max_offline_chunk: int = MAX_OFFLINE_CHUNK  # 1000字符

    # 离线优先 (否者在线优先)
    offline_first: bool = True

    # 并发数 (批量翻译)
    max_concurrency: int = 3

    # 回退策略
    fallback_to_online: bool = True
    fallback_to_offline: bool = True

    # 默认目标语言
    default_target_lang: str = "zh"

    # 翻译器选择
    preferred_offline: TranslatorType = TranslatorType.ARGOS
    preferred_online: TranslatorType = TranslatorType.DEEP_TRANSLATOR


class SmartTranslator:
    """
    智能分层翻译器

    使用策略:
    1. 短文本/单条: 离线优先 (Argos/EasyNMT)
    2. 长文本: 在线翻译 (DeepTranslator)
    3. 离线失败: 自动切换到在线
    4. 批量: 并行 + 智能分块
    """

    def __init__(self, config: Optional[SmartTranslateConfig] = None):
        """
        Args:
            config: 智能翻译配置
        """
        self.config = config or SmartTranslateConfig()

        # 子翻译器
        self._offline: Optional[OfflineTranslator] = None
        self._online: Optional[OnlineTranslator] = None

        # 统计
        self._stats = {
            "total_requests": 0,
            "offline_requests": 0,
            "online_requests": 0,
            "fallback_count": 0,
            "avg_offline_latency_ms": 0,
            "avg_online_latency_ms": 0,
        }

    def _get_offline(self) -> OfflineTranslator:
        """获取离线翻译器"""
        if self._offline is None:
            self._offline = get_offline_translator()
        return self._offline

    def _get_online(self) -> OnlineTranslator:
        """获取在线翻译器"""
        if self._online is None:
            self._online = get_online_translator()
        return self._online

    def _should_use_offline(self, text: str) -> bool:
        """判断是否应使用离线翻译"""
        char_count = len(text)

        # 超过离线最大长度, 必须用在线
        if char_count > self.config.max_offline_chunk:
            return False

        # 离线优先模式
        if self.config.offline_first:
            return char_count <= self.config.offline_threshold

        # 在线优先模式
        return char_count <= self.config.max_offline_chunk // 2

    def translate(self,
                  text: str,
                  source_lang: str = "auto",
                  target_lang: str = "zh",
                  force_type: Optional[TranslatorType] = None) -> TranslationResult:
        """
        翻译单条文本

        Args:
            text: 原文
            source_lang: 源语言
            target_lang: 目标语言
            force_type: 强制使用特定翻译器 (None=智能选择)

        Returns:
            TranslationResult 对象
        """
        start_time = time.time()
        self._stats["total_requests"] += 1

        # 规范化语言
        source_lang = normalize_language(source_lang)
        target_lang = normalize_language(target_lang)

        # 智能选择翻译器
        if force_type:
            translator_type = force_type
        elif self._should_use_offline(text):
            translator_type = self.config.preferred_offline
        else:
            translator_type = self.config.preferred_online

        # 尝试翻译
        try:
            if translator_type in (TranslatorType.ARGOS, TranslatorType.EASY_NMT, TranslatorType.HELSINKI):
                # 离线翻译
                result = self._translate_offline(text, source_lang, target_lang, translator_type)
                self._stats["offline_requests"] += 1
                self._update_avg_latency("offline", result.get_duration_ms())
            else:
                # 在线翻译
                result = self._translate_online(text, source_lang, target_lang, translator_type)
                self._stats["online_requests"] += 1
                self._update_avg_latency("online", result.get_duration_ms())

            return result

        except Exception as e:
            # 回退策略
            if self.config.fallback_to_online and translator_type in (
                TranslatorType.ARGOS, TranslatorType.EASY_NMT, TranslatorType.HELSINKI
            ):
                self._stats["fallback_count"] += 1
                try:
                    result = self._translate_online(text, source_lang, target_lang)
                    self._stats["online_requests"] += 1
                    return result
                except Exception:
                    pass

            elif self.config.fallback_to_offline and translator_type in (
                TranslatorType.DEEP_TRANSLATOR, TranslatorType.LIBRE_TRANSLATE
            ):
                self._stats["fallback_count"] += 1
                try:
                    result = self._translate_offline(text, source_lang, target_lang)
                    self._stats["offline_requests"] += 1
                    return result
                except Exception:
                    pass

            # 全部失败
            return TranslationResult(
                original=text,
                translated="",
                source_lang=source_lang,
                target_lang=target_lang,
                translator=TranslatorType.SMART,
                confidence=0
            )

    def _translate_offline(self,
                           text: str,
                           source_lang: str,
                           target_lang: str,
                           translator_type: TranslatorType = TranslatorType.ARGOS) -> TranslationResult:
        """使用离线翻译"""
        offline = self._get_offline()
        return offline.translate(text, source_lang, target_lang, translator_type)

    def _translate_online(self,
                         text: str,
                         source_lang: str,
                         target_lang: str,
                         translator_type: TranslatorType = TranslatorType.DEEP_TRANSLATOR) -> TranslationResult:
        """使用在线翻译"""
        online = self._get_online()
        return online.translate(text, source_lang, target_lang, translator_type)

    def _update_avg_latency(self, which: str, latency_ms: float):
        """更新平均延迟"""
        if which == "offline":
            avg = self._stats["avg_offline_latency_ms"]
            n = self._stats["offline_requests"]
            self._stats["avg_offline_latency_ms"] = (avg * (n - 1) + latency_ms) / n
        else:
            avg = self._stats["avg_online_latency_ms"]
            n = self._stats["online_requests"]
            self._stats["avg_online_latency_ms"] = (avg * (n - 1) + latency_ms) / n

    def translate_batch(self,
                        texts: List[str],
                        source_lang: str = "auto",
                        target_lang: str = "zh",
                        progress_callback: Optional[Callable] = None) -> BatchTranslationResult:
        """
        批量翻译

        Args:
            texts: 文本列表
            source_lang: 源语言
            target_lang: 目标语言
            progress_callback: 进度回调

        Returns:
            BatchTranslationResult 对象
        """
        start_time = time.time()
        results = []
        success_count = 0
        failed_count = 0

        # 智能分块: 根据文本长度分组
        offline_texts = []
        online_texts = []

        for text in texts:
            if self._should_use_offline(text):
                offline_texts.append(text)
            else:
                online_texts.append(text)

        # 并行翻译
        total = len(texts)
        completed = 0

        # 离线批量
        if offline_texts:
            try:
                offline = self._get_offline()
                offline_results = offline.translate_batch(
                    offline_texts,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    translator_type=self.config.preferred_offline
                )
                results.extend(offline_results)
                success_count += len([r for r in offline_results if r.confidence > 0])
            except Exception:
                # 离线失败, 逐条回退到在线
                for text in offline_texts:
                    try:
                        result = self._translate_online(text, source_lang, target_lang)
                        results.append(result)
                        success_count += 1
                    except Exception:
                        results.append(TranslationResult(
                            original=text,
                            translated="",
                            source_lang=source_lang,
                            target_lang=target_lang,
                            translator=TranslatorType.SMART,
                            confidence=0
                        ))
                        failed_count += 1
            completed += len(offline_texts)
            if progress_callback:
                progress_callback(completed / total)

        # 在线批量
        if online_texts:
            try:
                online = self._get_online()
                batch_result = online.translate_batch(
                    online_texts,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    translator_type=self.config.preferred_online
                )
                results.extend(batch_result.results)
                success_count += batch_result.success_count
                failed_count += batch_result.failed_count
            except Exception:
                # 在线失败, 逐条回退到离线
                for text in online_texts:
                    try:
                        result = self._translate_offline(text, source_lang, target_lang)
                        results.append(result)
                        success_count += 1
                    except Exception:
                        results.append(TranslationResult(
                            original=text,
                            translated="",
                            source_lang=source_lang,
                            target_lang=target_lang,
                            translator=TranslatorType.SMART,
                            confidence=0
                        ))
                        failed_count += 1
            completed += len(online_texts)
            if progress_callback:
                progress_callback(completed / total)

        total_latency = (time.time() - start_time) * 1000

        return BatchTranslationResult(
            results=results,
            total_count=total,
            success_count=success_count,
            failed_count=failed_count,
            total_latency_ms=total_latency
        )

    async def translate_batch_async(self,
                                    texts: List[str],
                                    source_lang: str = "auto",
                                    target_lang: str = "zh",
                                    progress_callback: Optional[Callable] = None) -> BatchTranslationResult:
        """
        异步批量翻译

        Args:
            texts: 文本列表
            source_lang: 源语言
            target_lang: 目标语言
            progress_callback: 进度回调

        Returns:
            BatchTranslationResult 对象
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.translate_batch,
            texts, source_lang, target_lang, progress_callback
        )

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self._stats,
            "offline_available": self._get_offline().is_available(),
            "online_available": self._get_online().is_available(),
            "offline_translators": [t.type.value for t in self._get_offline().get_available_translators()],
            "online_translators": [t.type.value for t in self._get_online().get_available_translators()],
        }

    def get_best_translator(self) -> Tuple[TranslatorType, str]:
        """
        获取最佳翻译器

        Returns:
            (TranslatorType, 说明)
        """
        offline = self._get_offline()
        online = self._get_online()

        if offline.is_available() and online.is_available():
            return (TranslatorType.SMART, "智能分层 (离线优先 + 在线兜底)")
        elif offline.is_available():
            return (self.config.preferred_offline, "离线翻译 (Argos/EasyNMT)")
        elif online.is_available():
            return (self.config.preferred_online, "在线翻译 (DeepTranslator)")
        else:
            return (TranslatorType.SMART, "无可用翻译器")

    def close(self):
        """关闭所有翻译器"""
        if self._offline:
            self._offline.close()
            self._offline = None
        if self._online:
            self._online.close()
            self._online = None


# 单例
_smart_translator: Optional[SmartTranslator] = None


def get_smart_translator(config: Optional[SmartTranslateConfig] = None) -> SmartTranslator:
    """获取智能翻译器单例"""
    global _smart_translator
    if _smart_translator is None:
        _smart_translator = SmartTranslator(config)
    return _smart_translator
