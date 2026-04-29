"""
Translator - 翻译引擎
=====================

支持多种翻译引擎：
- Ollama (本地，推荐)
- OpenAI GPT
- Google Translate
- DeepL
- 自定义 API
"""

import re
import time
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from enum import Enum


class TranslationProvider(Enum):
    """翻译提供商"""
    OLLAMA = "ollama"           # 本地 Ollama
    OPENAI = "openai"           # OpenAI GPT
    GOOGLE = "google"           # Google Translate
    DEEPL = "deepl"             # DeepL
    BAIDU = "baidu"             # 百度翻译
    TENCENT = "tencent"         # 腾讯翻译
    CUSTOM = "custom"           # 自定义 API


@dataclass
class TranslationResult:
    """翻译结果"""
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    provider: TranslationProvider
    model: Optional[str] = None
    tokens_used: int = 0
    processing_time: float = 0.0
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.error is None


@dataclass
class BatchTranslationResult:
    """批量翻译结果"""
    results: List[TranslationResult]
    total_segments: int
    successful: int
    failed: int
    total_time: float

    @property
    def success_rate(self) -> float:
        if self.total_segments == 0:
            return 0.0
        return self.successful / self.total_segments


class BaseTranslator(ABC):
    """翻译器基类"""

    def __init__(self, provider: TranslationProvider):
        self.provider = provider
        self._glossary: Dict[str, str] = {}

    def set_glossary(self, glossary: Dict[str, str]):
        """设置术语表"""
        self._glossary = glossary

    def _apply_glossary(self, text: str) -> str:
        """应用术语表"""
        result = text
        for source, target in self._glossary.items():
            result = result.replace(source, target)
        return result

    @abstractmethod
    async def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        """翻译单段文本"""
        pass

    async def batch_translate(self, texts: List[str], source_lang: str,
                            target_lang: str, progress: Optional[Callable] = None,
                            delay: float = 0) -> BatchTranslationResult:
        """批量翻译"""
        results = []
        start_time = time.time()
        successful = 0
        failed = 0

        for i, text in enumerate(texts):
            if progress:
                progress(i + 1, len(texts), f"翻译第 {i+1}/{len(texts)} 段...")

            result = await self.translate(text, source_lang, target_lang)
            results.append(result)

            if result.is_success:
                successful += 1
            else:
                failed += 1

            # 添加延迟避免 API 限流
            if delay > 0 and i < len(texts) - 1:
                await asyncio.sleep(delay)

        total_time = time.time() - start_time
        return BatchTranslationResult(
            results=results,
            total_segments=len(texts),
            successful=successful,
            failed=failed,
            total_time=total_time
        )


class OllamaTranslator(BaseTranslator):
    """Ollama 本地翻译器 (推荐)"""

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "llama3.2", timeout: float = 120.0):
        super().__init__(TranslationProvider.OLLAMA)
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        """获取 Ollama 客户端"""
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(timeout=self.timeout)
            except ImportError:
                return None
        return self._client

    async def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        """使用 Ollama 翻译"""
        start_time = time.time()

        # 构建提示词
        prompt = self._build_prompt(text, source_lang, target_lang)

        try:
            client = self._get_client()
            if client is None:
                return TranslationResult(
                    original_text=text,
                    translated_text="",
                    source_lang=source_lang,
                    target_lang=target_lang,
                    provider=self.provider,
                    error="httpx 未安装，请运行: pip install httpx"
                )

            # Ollama API 调用
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9
                    }
                }
            )
            response.raise_for_status()

            data = response.json()
            translated = data.get("response", "").strip()

            # 清理响应
            translated = self._clean_response(translated)

            return TranslationResult(
                original_text=text,
                translated_text=translated,
                source_lang=source_lang,
                target_lang=target_lang,
                provider=self.provider,
                model=self.model,
                processing_time=time.time() - start_time
            )

        except Exception as e:
            return TranslationResult(
                original_text=text,
                translated_text="",
                source_lang=source_lang,
                target_lang=target_lang,
                provider=self.provider,
                error=str(e),
                processing_time=time.time() - start_time
            )

    def _build_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
        """构建翻译提示词"""
        lang_names = {
            'en': 'English', 'zh': 'Chinese', 'ja': 'Japanese',
            'ko': 'Korean', 'fr': 'French', 'de': 'German',
            'es': 'Spanish', 'ru': 'Russian', 'ar': 'Arabic'
        }

        src_name = lang_names.get(source_lang, source_lang)
        tgt_name = lang_names.get(target_lang, target_lang)

        return f"""Translate the following text from {src_name} to {tgt_name}.
Only output the translated text, no explanations.

Text:
{text}

Translation:"""


class OpenAITranslator(BaseTranslator):
    """OpenAI GPT 翻译器"""

    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo",
                 base_url: str = "https://api.openai.com/v1"):
        super().__init__(TranslationProvider.OPENAI)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip('/')
        self._client = None

    def _get_client(self):
        """获取 OpenAI 客户端"""
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=60.0
                )
            except ImportError:
                return None
        return self._client

    async def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        """使用 OpenAI 翻译"""
        start_time = time.time()

        prompt = self._build_prompt(text, source_lang, target_lang)

        try:
            client = self._get_client()
            if client is None:
                return TranslationResult(
                    original_text=text,
                    translated_text="",
                    source_lang=source_lang,
                    target_lang=target_lang,
                    provider=self.provider,
                    error="httpx 未安装"
                )

            response = await client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a professional translator."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3
                }
            )
            response.raise_for_status()

            data = response.json()
            translated = data["choices"][0]["message"]["content"].strip()
            tokens = data.get("usage", {}).get("total_tokens", 0)

            return TranslationResult(
                original_text=text,
                translated_text=translated,
                source_lang=source_lang,
                target_lang=target_lang,
                provider=self.provider,
                model=self.model,
                tokens_used=tokens,
                processing_time=time.time() - start_time
            )

        except Exception as e:
            return TranslationResult(
                original_text=text,
                translated_text="",
                source_lang=source_lang,
                target_lang=target_lang,
                provider=self.provider,
                error=str(e),
                processing_time=time.time() - start_time
            )

    def _build_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
        """构建翻译提示词"""
        return f"""Translate the following text to {target_lang}. Only output the translation.

Text: {text}

Translation:"""


class GoogleTranslator(BaseTranslator):
    """Google Translate 翻译器"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(TranslationProvider.GOOGLE)
        self.api_key = api_key

    async def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        """使用 Google Translate 翻译"""
        start_time = time.time()

        try:
            # 尝试使用 googletrans 库
            from googletrans import Translator as GoogleTrans
            translator = GoogleTrans()

            # 处理语言代码
            src_code = 'auto' if source_lang == 'auto' else source_lang
            tgt_code = target_lang

            result = translator.translate(text, src=src_code, dest=tgt_code)

            return TranslationResult(
                original_text=text,
                translated_text=result.text,
                source_lang=source_lang,
                target_lang=target_lang,
                provider=self.provider,
                model="google-translate",
                processing_time=time.time() - start_time
            )

        except ImportError:
            return TranslationResult(
                original_text=text,
                translated_text="",
                source_lang=source_lang,
                target_lang=target_lang,
                provider=self.provider,
                error="googletrans 未安装，请运行: pip install googletrans"
            )
        except Exception as e:
            return TranslationResult(
                original_text=text,
                translated_text="",
                source_lang=source_lang,
                target_lang=target_lang,
                provider=self.provider,
                error=str(e),
                processing_time=time.time() - start_time
            )


class MockTranslator(BaseTranslator):
    """模拟翻译器 (用于测试)"""

    def __init__(self):
        super().__init__(TranslationProvider.CUSTOM)

    async def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        """模拟翻译"""
        start_time = time.time()

        # 简单的模拟翻译
        mock_translations = {
            ('en', 'zh'): f"[ZH] {text}",
            ('zh', 'en'): f"[EN] {text}",
            ('en', 'ja'): f"[JA] {text}",
            ('ja', 'en'): f"[EN] {text}",
        }

        key = (source_lang, target_lang)
        translated = mock_translations.get(key, f"[{target_lang.upper()}] {text}")

        return TranslationResult(
            original_text=text,
            translated_text=translated,
            source_lang=source_lang,
            target_lang=target_lang,
            provider=self.provider,
            model="mock",
            processing_time=time.time() - start_time
        )


class Translator:
    """翻译器管理器"""

    def __init__(self):
        self._translators: Dict[TranslationProvider, BaseTranslator] = {}
        self._default_provider = TranslationProvider.OLLAMA

    def register_translator(self, translator: BaseTranslator):
        """注册翻译器"""
        self._translators[translator.provider] = translator

    def set_default(self, provider: TranslationProvider):
        """设置默认翻译器"""
        self._default_provider = provider

    def get_translator(self, provider: Optional[TranslationProvider] = None) -> BaseTranslator:
        """获取翻译器"""
        if provider is None:
            provider = self._default_provider

        if provider in self._translators:
            return self._translators[provider]

        # 返回默认或模拟翻译器
        if provider == TranslationProvider.OLLAMA:
            translator = OllamaTranslator()
            self._translators[provider] = translator
            return translator
        elif provider == TranslationProvider.OPENAI:
            # 返回模拟器，需要配置 API key
            translator = MockTranslator()
            self._translators[provider] = translator
            return translator

        # 返回模拟翻译器作为后备
        return MockTranslator()

    async def translate(self, text: str, source_lang: str, target_lang: str,
                       provider: Optional[TranslationProvider] = None) -> TranslationResult:
        """翻译文本"""
        translator = self.get_translator(provider)
        return await translator.translate(text, source_lang, target_lang)

    async def translate_document(self, texts: List[str], source_lang: str,
                                 target_lang: str,
                                 provider: Optional[TranslationProvider] = None,
                                 progress: Optional[Callable] = None) -> BatchTranslationResult:
        """翻译文档段落"""
        translator = self.get_translator(provider)

        # 智能分段
        segments = self._segment_texts(texts)

        return await translator.batch_translate(
            segments, source_lang, target_lang,
            progress=progress, delay=0.5
        )

    def _segment_texts(self, texts: List[str], max_length: int = 500) -> List[str]:
        """将文本分割成适合翻译的长度"""
        segments = []

        for text in texts:
            if len(text) <= max_length:
                segments.append(text)
            else:
                # 按段落分割
                paragraphs = text.split('\n')
                current = []

                for para in paragraphs:
                    current_len = sum(len(p) for p in current)
                    if current_len + len(para) <= max_length:
                        current.append(para)
                    else:
                        if current:
                            segments.append('\n'.join(current))
                        current = [para]

                if current:
                    segments.append('\n'.join(current))

        return segments


# 便捷函数
async def quick_translate(text: str, source_lang: str = 'en',
                          target_lang: str = 'zh',
                          provider: TranslationProvider = TranslationProvider.OLLAMA) -> str:
    """快速翻译"""
    translator = Translator()
    result = await translator.translate(text, source_lang, target_lang, provider)
    if result.is_success:
        return result.translated_text
    raise ValueError(result.error or "Translation failed")
