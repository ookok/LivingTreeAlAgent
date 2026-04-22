"""
翻译核心调度器 - Translation Hub
整合所有翻译模块, 提供统一的翻译服务接口

功能:
1. 智能分层翻译 (离线优先 + 在线兜底)
2. 翻译历史记录
3. 翻译缓存
4. 与搜索/情报系统集成
"""

import time
import asyncio
import hashlib
from typing import Optional, List, Dict, Callable, Any
from dataclasses import dataclass, field
from pathlib import Path

from .models import (
    TranslatorType, TranslatorStatus,
    TranslationTask, TranslationResult, BatchTranslationResult,
    Language, LANGUAGE_NAMES, normalize_language,
    BATCH_SIZE_THRESHOLD
)
from .smart_translator import SmartTranslator, get_smart_translator, SmartTranslateConfig
from .offline_translator import get_offline_translator
from .online_translator import get_online_translator


@dataclass
class CacheEntry:
    """缓存条目"""
    original_hash: str       # 原文哈希
    translated: str          # 译文
    source_lang: str          # 源语言
    target_lang: str          # 目标语言
    translator: TranslatorType  # 使用的翻译器
    timestamp: float = field(default_factory=time.time)
    hit_count: int = 0        # 命中次数


class TranslationHub:
    """
    翻译核心调度器

    设计目标:
    1. 统一接口: 单条/批量/流式翻译
    2. 智能路由: 根据文本长度和质量选择最佳翻译器
    3. 缓存加速: 避免重复翻译相同内容
    4. 统计监控: 追踪翻译质量和性能
    5. 搜索集成: 外网搜索结果自动翻译

    使用场景:
    1. 搜索结果翻译 (外网 → 中文)
    2. 文档翻译 (长文本)
    3. 实时对话翻译
    4. 离线优先场景
    """

    _instance: Optional['TranslationHub'] = None

    def __init__(self, config: Optional[SmartTranslateConfig] = None):
        """单例模式"""
        if TranslationHub._instance is not None:
            raise RuntimeError("TranslationHub is singleton, use get_translation_hub()")

        # 智能翻译器
        self._smart_translator: Optional[SmartTranslator] = None
        self._config = config or SmartTranslateConfig()

        # 缓存 (内存缓存, 可选持久化)
        self._cache: Dict[str, CacheEntry] = {}
        self._cache_enabled = True
        self._cache_max_size = 1000

        # 翻译历史
        self._history: List[TranslationTask] = []
        self._history_max_size = 100

        # UI 回调
        self._callbacks: List[Callable] = []

        # 统计
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_chars": 0,
            "avg_latency_ms": 0,
        }

    @classmethod
    def get_translation_hub(cls, config: Optional[SmartTranslateConfig] = None) -> 'TranslationHub':
        """获取 TranslationHub 单例"""
        if cls._instance is None:
            cls._instance = TranslationHub(config)
        return cls._instance

    # ============ 翻译接口 ============

    def translate(self,
                  text: str,
                  source_lang: str = "auto",
                  target_lang: str = "zh",
                  use_cache: bool = True) -> TranslationResult:
        """
        翻译单条文本

        Args:
            text: 原文
            source_lang: 源语言 (默认自动检测)
            target_lang: 目标语言 (默认中文)
            use_cache: 是否使用缓存

        Returns:
            TranslationResult 对象
        """
        # 检查缓存
        if use_cache and self._cache_enabled:
            cache_key = self._make_cache_key(text, source_lang, target_lang)
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                entry.hit_count += 1
                self._stats["cache_hits"] += 1
                return TranslationResult(
                    original=text,
                    translated=entry.translated,
                    source_lang=entry.source_lang,
                    target_lang=entry.target_lang,
                    translator=entry.translator,
                    confidence=0.95  # 缓存命中, 高置信度
                )

        self._stats["cache_misses"] += 1
        self._stats["total_requests"] += 1
        self._stats["total_chars"] += len(text)

        # 获取翻译器
        smart = self._get_smart_translator()
        start_time = time.time()

        # 执行翻译
        result = smart.translate(text, source_lang, target_lang)

        # 更新延迟统计
        latency = (time.time() - start_time) * 1000
        n = self._stats["total_requests"]
        self._stats["avg_latency_ms"] = (self._stats["avg_latency_ms"] * (n - 1) + latency) / n

        # 存入缓存
        if use_cache and self._cache_enabled and result.translated:
            self._add_to_cache(text, result, source_lang, target_lang)

        # 添加到历史
        self._add_to_history(text, source_lang, target_lang, result)

        # 通知回调
        self._notify("translated", result)

        return result

    async def translate_async(self,
                              text: str,
                              source_lang: str = "auto",
                              target_lang: str = "zh",
                              use_cache: bool = True) -> TranslationResult:
        """异步翻译"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.translate,
            text, source_lang, target_lang, use_cache
        )

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
        self._stats["total_requests"] += len(texts)
        self._stats["total_chars"] += sum(len(t) for t in texts)

        # 获取翻译器
        smart = self._get_smart_translator()

        # 执行批量翻译
        result = smart.translate_batch(texts, source_lang, target_lang, progress_callback)

        # 缓存成功的翻译
        if self._cache_enabled:
            for r in result.results:
                if r.translated and r.confidence > 0.5:
                    self._add_to_cache(r.original, r, source_lang, target_lang)

        # 添加到历史
        for r in result.results:
            self._add_to_history(r.original, source_lang, target_lang, r)

        # 通知回调
        self._notify("batch_translated", result)

        return result

    async def translate_batch_async(self,
                                     texts: List[str],
                                     source_lang: str = "auto",
                                     target_lang: str = "zh",
                                     progress_callback: Optional[Callable] = None) -> BatchTranslationResult:
        """异步批量翻译"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.translate_batch,
            texts, source_lang, target_lang, progress_callback
        )

    # ============ 搜索集成 ============

    def translate_search_results(self,
                                results: List[Dict[str, Any]],
                                text_field: str = "text",
                                target_lang: str = "zh") -> List[Dict[str, Any]]:
        """
        翻译搜索结果

        Args:
            results: 搜索结果列表 (每项是 dict)
            text_field: 要翻译的字段名
            target_lang: 目标语言

        Returns:
            翻译后的搜索结果
        """
        translated_results = []

        for item in results:
            # 深拷贝
            new_item = dict(item)

            # 翻译指定字段
            if text_field in item:
                original_text = str(item[text_field])
                if len(original_text) > 10:  # 只翻译有意义的文本
                    result = self.translate(original_text, target_lang=target_lang)
                    new_item[f"{text_field}_translated"] = result.translated
                    new_item["_translation_confidence"] = result.confidence

            translated_results.append(new_item)

        return translated_results

    async def translate_search_results_async(self,
                                             results: List[Dict[str, Any]],
                                             text_field: str = "text",
                                             target_lang: str = "zh") -> List[Dict[str, Any]]:
        """异步翻译搜索结果"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.translate_search_results,
            results, text_field, target_lang
        )

    # ============ 缓存管理 ============

    def _make_cache_key(self, text: str, source_lang: str, target_lang: str) -> str:
        """生成缓存 key"""
        content = f"{text}|{source_lang}|{target_lang}"
        return hashlib.md5(content.encode()).hexdigest()

    def _add_to_cache(self,
                      text: str,
                      result: TranslationResult,
                      source_lang: str,
                      target_lang: str):
        """添加到缓存"""
        cache_key = self._make_cache_key(text, source_lang, target_lang)

        self._cache[cache_key] = CacheEntry(
            original_hash=cache_key,
            translated=result.translated,
            source_lang=source_lang,
            target_lang=target_lang,
            translator=result.translator
        )

        # 清理过期缓存
        if len(self._cache) > self._cache_max_size:
            self._cleanup_cache()

    def _cleanup_cache(self):
        """清理缓存 (LRU)"""
        if not self._cache:
            return

        # 按命中次数排序, 删除最不常用的
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].hit_count
        )

        # 删除最少的 10%
        remove_count = max(1, len(sorted_entries) // 10)
        for key, _ in sorted_entries[:remove_count]:
            del self._cache[key]

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        total_hits = sum(e.hit_count for e in self._cache.values())
        return {
            "size": len(self._cache),
            "max_size": self._cache_max_size,
            "total_hits": total_hits,
            "hit_rate": self._stats["cache_hits"] / (self._stats["cache_hits"] + self._stats["cache_misses"])
                        if (self._stats["cache_hits"] + self._stats["cache_misses"]) > 0 else 0
        }

    # ============ 历史记录 ============

    def _add_to_history(self,
                        text: str,
                        source_lang: str,
                        target_lang: str,
                        result: TranslationResult):
        """添加到历史"""
        task = TranslationTask(
            task_id=hashlib.md5(str(time.time()).encode()).hexdigest()[:8],
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            translator_type=result.translator,
            translated_text=result.translated,
            status=TranslatorStatus.AVAILABLE if result.confidence > 0 else TranslatorStatus.ERROR,
            char_count=len(text),
            created_at=time.time(),
            completed_at=time.time()
        )

        self._history.insert(0, task)

        # 限制历史长度
        if len(self._history) > self._history_max_size:
            self._history = self._history[:self._history_max_size]

    def get_history(self, limit: int = 20) -> List[TranslationTask]:
        """获取翻译历史"""
        return self._history[:limit]

    def clear_history(self):
        """清空历史"""
        self._history.clear()

    # ============ 统计监控 ============

    def get_stats(self) -> Dict:
        """获取统计信息"""
        smart = self._get_smart_translator()
        return {
            **self._stats,
            "cache": self.get_cache_stats(),
            "smart_translator": smart.get_stats(),
            "best_translator": smart.get_best_translator()[1],
        }

    # ============ 辅助方法 ============

    def _get_smart_translator(self) -> SmartTranslator:
        """获取智能翻译器"""
        if self._smart_translator is None:
            self._smart_translator = get_smart_translator(self._config)
        return self._smart_translator

    def get_available_translators(self) -> List[Dict]:
        """获取可用的翻译器列表"""
        offline = get_offline_translator()
        online = get_online_translator()

        result = []

        for info in offline.get_available_translators():
            result.append({
                "name": info.name,
                "type": info.type.value,
                "is_offline": True,
                "languages": info.languages,
                "model_size": info.model_size,
            })

        for info in online.get_available_translators():
            result.append({
                "name": info.name,
                "type": info.type.value,
                "is_offline": False,
                "languages": info.languages,
            })

        return result

    def detect_language(self, text: str) -> str:
        """检测语言 (使用 langdetect 库)"""
        if not text or not text.strip():
            return "en"
        
        try:
            # 尝试使用 langdetect 库进行语言检测
            from langdetect import detect, LangDetectException
            
            # langdetect 需要至少 100 个字符才能准确检测
            # 如果文本太短，先检测是否包含非 ASCII 字符
            detected = detect(text)
            
            # 将 langdetect 的语言代码转换为 ISO 639-1 格式
            lang_map = {
                'zh': 'zh-CN',
                'ja': 'ja',
                'ko': 'ko',
                'ru': 'ru',
                'ar': 'ar',
                'en': 'en',
                'fr': 'fr',
                'de': 'de',
                'es': 'es',
                'pt': 'pt',
                'it': 'it',
                'nl': 'nl',
                'pl': 'pl',
                'tr': 'tr',
                'vi': 'vi',
                'th': 'th',
                'id': 'id',
            }
            
            return lang_map.get(detected, detected)
            
        except ImportError:
            # langdetect 未安装，降级使用正则表达式检测
            logger.debug("langdetect 未安装，使用正则表达式检测语言")
            return self._detect_language_regex(text)
        except LangDetectException:
            # 检测失败，降级使用正则表达式
            return self._detect_language_regex(text)
        except Exception:
            # 其他异常，返回英语
            return "en"
    
    def _detect_language_regex(self, text: str) -> str:
        """使用正则表达式检测语言（降级方案）"""
        import re
        
        # 中文检测
        if re.search(r'[\u4e00-\u9fff]', text):
            return "zh-CN"
        
        # 日语检测
        if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
            return "ja"
        
        # 韩语检测
        if re.search(r'[\uac00-\ud7af]', text):
            return "ko"
        
        # 俄语检测
        if re.search(r'[\u0400-\u04ff]', text):
            return "ru"
        
        # 阿拉伯语检测
        if re.search(r'[\u0600-\u06ff]', text):
            return "ar"
        
        # 默认英语
        return "en"

    # ============ UI 回调 ============

    def add_callback(self, callback: Callable):
        """添加回调"""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        """移除回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify(self, event: str, data: Any):
        """通知回调"""
        for cb in self._callbacks:
            try:
                cb(event, data)
            except Exception as e:
                print(f"[TranslationHub] Callback error: {e}")

    # ============ 配置 ============

    def set_config(self, config: SmartTranslateConfig):
        """设置配置"""
        self._config = config
        # 重新创建翻译器
        if self._smart_translator:
            self._smart_translator.close()
            self._smart_translator = None

    def enable_cache(self, enabled: bool = True):
        """启用/禁用缓存"""
        self._cache_enabled = enabled

    # ============ 生命周期 ============

    def close(self):
        """关闭"""
        if self._smart_translator:
            self._smart_translator.close()
            self._smart_translator = None
        TranslationHub._instance = None


# 全局访问函数
_translation_hub: Optional[TranslationHub] = None


def get_translation_hub(config: Optional[SmartTranslateConfig] = None) -> TranslationHub:
    """获取 TranslationHub 单例"""
    global _translation_hub
    if _translation_hub is None:
        _translation_hub = TranslationHub.get_translation_hub(config)
    return _translation_hub
