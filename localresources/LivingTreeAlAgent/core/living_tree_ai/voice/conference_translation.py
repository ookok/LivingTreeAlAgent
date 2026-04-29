"""
多语言同声传译模块

支持多语言会议的实时翻译和同声传译
"""

import asyncio
from typing import Optional, Dict, List, Callable, Set
from dataclasses import dataclass
from enum import Enum
import uuid


class Language(Enum):
    """支持的语言"""
    CHINESE = "zh"
    ENGLISH = "en"
    JAPANESE = "ja"
    KOREAN = "ko"
    FRENCH = "fr"
    GERMAN = "de"
    SPANISH = "es"
    RUSSIAN = "ru"
    ARABIC = "ar"
    PORTUGUESE = "pt"


LANGUAGE_NAMES = {
    "zh": "中文",
    "en": "英文",
    "ja": "日文",
    "ko": "韩文",
    "fr": "法文",
    "de": "德文",
    "es": "西班牙文",
    "ru": "俄文",
    "ar": "阿拉伯文",
    "pt": "葡萄牙文"
}


@dataclass
class TranslationResult:
    """翻译结果"""
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    confidence: float
    is_final: bool
    timestamp: float


@dataclass
class ParticipantLanguage:
    """参与者的语言偏好"""
    participant_id: str
    language: str
    needs_interpretation: bool = True


class TranslationService:
    """翻译服务"""

    def __init__(self):
        self.translators: Dict[str, any] = {}
        self._is_initialized = False

    async def initialize(self) -> bool:
        """
        初始化翻译服务

        Returns:
            bool: 是否初始化成功
        """
        if self._is_initialized:
            return True

        try:
            try:
                from transformers import pipeline
                self.translators["transformers"] = pipeline(
                    "translation",
                    model="Helsinki-NLP/opus-mt-ZH-en",
                    device=-1
                )
                print("[Translation] Helsinki-NLP 翻译模型加载成功")
            except ImportError:
                print("[Translation] transformers 未安装，将使用模拟翻译")

            self._is_initialized = True
            return True

        except Exception as e:
            print(f"[Translation] 初始化失败: {e}")
            return False

    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str
    ) -> Optional[TranslationResult]:
        """
        翻译文本

        Args:
            text: 源文本
            source_language: 源语言
            target_language: 目标语言

        Returns:
            Optional[TranslationResult]: 翻译结果
        """
        if source_language == target_language:
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language,
                target_language=target_language,
                confidence=1.0,
                is_final=True,
                timestamp=asyncio.get_event_loop().time()
            )

        try:
            if "transformers" in self.translators:
                translator = self.translators["transformers"]
                result = translator(text)
                translated = result[0]["translation_text"]
            else:
                translated = f"[翻译] {text}"

            return TranslationResult(
                original_text=text,
                translated_text=translated,
                source_language=source_language,
                target_language=target_language,
                confidence=0.9,
                is_final=True,
                timestamp=asyncio.get_event_loop().time()
            )

        except Exception as e:
            print(f"[Translation] 翻译失败: {e}")
            return None

    async def translate_to_multiple(
        self,
        text: str,
        source_language: str,
        target_languages: List[str]
    ) -> Dict[str, TranslationResult]:
        """
        翻译到多种语言

        Args:
            text: 源文本
            source_language: 源语言
            target_languages: 目标语言列表

        Returns:
            Dict[str, TranslationResult]: 翻译结果字典
        """
        results = {}

        translate_tasks = [
            self.translate(text, source_language, target)
            for target in target_languages
        ]

        translations = await asyncio.gather(*translate_tasks)

        for target, result in zip(target_languages, translations):
            if result:
                results[target] = result

        return results


class SimultaneousInterpretation:
    """同声传译系统"""

    def __init__(self, translation_service: Optional[TranslationService] = None):
        self.translation_service = translation_service or TranslationService()
        self.participant_languages: Dict[str, ParticipantLanguage] = {}
        self._is_running = False
        self._interpretation_callback: Optional[Callable] = None
        self._current_interpretations: Dict[str, str] = {}

    async def initialize(self) -> bool:
        """初始化"""
        return await self.translation_service.initialize()

    def add_participant(
        self,
        participant_id: str,
        language: str,
        needs_interpretation: bool = True
    ) -> bool:
        """
        添加参与者

        Args:
            participant_id: 参与者 ID
            language: 语言
            needs_interpretation: 是否需要翻译

        Returns:
            bool: 是否成功
        """
        participant = ParticipantLanguage(
            participant_id=participant_id,
            language=language,
            needs_interpretation=needs_interpretation
        )
        self.participant_languages[participant_id] = participant
        return True

    def remove_participant(self, participant_id: str) -> bool:
        """移除参与者"""
        if participant_id in self.participant_languages:
            del self.participant_languages[participant_id]
            return True
        return False

    def get_languages_needed(self) -> Set[str]:
        """获取需要的语言"""
        return {
            p.language for p in self.participant_languages.values()
            if p.needs_interpretation
        }

    async def interpret_speech(
        self,
        speaker_id: str,
        original_text: str,
        original_language: str
    ) -> Dict[str, TranslationResult]:
        """
        解释演讲

        Args:
            speaker_id: 演讲者 ID
            original_text: 原始文本
            original_language: 原始语言

        Returns:
            Dict[str, TranslationResult]: 各语言的翻译结果
        """
        target_languages = self.get_languages_needed()

        if original_language in target_languages:
            target_languages.discard(original_language)

        if not target_languages:
            return {}

        results = await self.translation_service.translate_to_multiple(
            original_text,
            original_language,
            list(target_languages)
        )

        self._current_interpretations = {
            lang: result.translated_text
            for lang, result in results.items()
        }

        return results

    async def start_interpretation(
        self,
        callback: Callable[[str, str, TranslationResult], None]
    ):
        """
        开始同声传译

        Args:
            callback: 回调函数 (participant_id, language, translation_result)
        """
        await self.initialize()
        self._is_running = True
        self._interpretation_callback = callback

    async def stop_interpretation(self):
        """停止同声传译"""
        self._is_running = False
        self._interpretation_callback = None

    def get_current_interpretation(self, language: str) -> Optional[str]:
        """获取当前翻译"""
        return self._current_interpretations.get(language)


class ConferenceTranslator:
    """会议翻译器"""

    def __init__(self):
        self.translation_service = TranslationService()
        self.sim_interpretation = SimultaneousInterpretation(self.translation_service)
        self._meeting_transcripts: Dict[str, List[Dict]] = {}
        self._current_meeting_id: Optional[str] = None

    async def initialize(self) -> bool:
        """初始化"""
        return await self.translation_service.initialize()

    def start_meeting(self, meeting_id: str):
        """开始会议翻译"""
        self._current_meeting_id = meeting_id
        self._meeting_transcripts[meeting_id] = []

    def end_meeting(self) -> Optional[str]:
        """结束会议翻译"""
        if not self._current_meeting_id:
            return None

        meeting_id = self._current_meeting_id
        self._current_meeting_id = None
        return meeting_id

    async def process_speech(
        self,
        speaker_id: str,
        speaker_name: str,
        text: str,
        language: str
    ) -> Dict[str, TranslationResult]:
        """
        处理演讲

        Args:
            speaker_id: 演讲者 ID
            speaker_name: 演讲者名称
            text: 文本
            language: 语言

        Returns:
            Dict[str, TranslationResult]: 翻译结果
        """
        if self._current_meeting_id:
            self._meeting_transcripts[self._current_meeting_id].append({
                "speaker_id": speaker_id,
                "speaker_name": speaker_name,
                "text": text,
                "language": language,
                "timestamp": asyncio.get_event_loop().time()
            })

        results = await self.sim_interpretation.interpret_speech(
            speaker_id, text, language
        )

        return results

    def get_meeting_transcript(
        self,
        meeting_id: Optional[str] = None,
        target_language: Optional[str] = None
    ) -> List[Dict]:
        """
        获取会议记录

        Args:
            meeting_id: 会议 ID
            target_language: 目标语言

        Returns:
            List[Dict]: 会议记录
        """
        meeting_id = meeting_id or self._current_meeting_id
        if not meeting_id or meeting_id not in self._meeting_transcripts:
            return []

        transcripts = self._meeting_transcripts[meeting_id]

        if not target_language:
            return transcripts

        return [
            {
                **t,
                "translated_text": self._find_translation(t, target_language)
            }
            for t in transcripts
        ]

    def _find_translation(self, transcript: Dict, target_language: str) -> Optional[str]:
        """查找翻译"""
        return None


class LanguageDetector:
    """语言检测器"""

    def __init__(self):
        self.model = None
        self._is_initialized = False

    async def initialize(self) -> bool:
        """初始化"""
        if self._is_initialized:
            return True

        try:
            from langdetect import detect
            self._detect = detect
            self._is_initialized = True
            return True
        except ImportError:
            print("[LanguageDetector] langdetect 未安装，将使用简单检测")
            self._detect = self._simple_detect
            self._is_initialized = True
            return True

    def detect(self, text: str) -> str:
        """
        检测语言

        Args:
            text: 文本

        Returns:
            str: 语言代码
        """
        if not self._is_initialized:
            asyncio.run(self.initialize())

        try:
            return self._detect(text)
        except:
            return self._simple_detect(text)

    def _simple_detect(self, text: str) -> str:
        """简单语言检测"""
        if not text:
            return "unknown"

        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        japanese_chars = sum(1 for c in text if '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff')
        korean_chars = sum(1 for c in text if '\uac00' <= c <= '\ud7af')

        total = len(text)
        if chinese_chars / total > 0.3:
            return "zh"
        elif japanese_chars / total > 0.3:
            return "ja"
        elif korean_chars / total > 0.3:
            return "ko"

        return "en"


_global_translator: Optional[ConferenceTranslator] = None


def get_conference_translator() -> ConferenceTranslator:
    """获取会议翻译器"""
    global _global_translator
    if _global_translator is None:
        _global_translator = ConferenceTranslator()
    return _global_translator
