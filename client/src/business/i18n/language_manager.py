#!/usr/bin/env python3
"""
i18n 多语言引擎 - Internationalization Engine
Phase 6 核心：多语言支持、本地化、翻译管理

Author: LivingTreeAI Team
Version: 1.0.0
"""

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import threading


class Language(Enum):
    """支持的语言"""
    EN = "en"           # 英语
    ZH_CN = "zh-CN"     # 简体中文
    ZH_TW = "zh-TW"     # 繁体中文
    JA = "ja"          # 日语
    KO = "ko"          # 韩语
    ES = "es"          # 西班牙语
    FR = "fr"          # 法语
    DE = "de"          # 德语
    PT = "pt"          # 葡萄牙语
    RU = "ru"          # 俄语
    AR = "ar"          # 阿拉伯语
    HI = "hi"          # 印地语


class LanguageInfo:
    """语言信息"""
    
    def __init__(self, code: str, name: str, native_name: str, direction: str = "ltr"):
        self.code = code
        self.name = name
        self.native_name = native_name
        self.direction = direction  # ltr (左到右) or rtl (右到左)
    
    def __repr__(self) -> str:
        return f"{self.name} ({self.native_name})"


# 语言信息注册表
LANGUAGE_INFO: Dict[str, LanguageInfo] = {
    "en": LanguageInfo("en", "English", "English"),
    "zh-CN": LanguageInfo("zh-CN", "Chinese (Simplified)", "简体中文"),
    "zh-TW": LanguageInfo("zh-TW", "Chinese (Traditional)", "繁體中文"),
    "ja": LanguageInfo("ja", "Japanese", "日本語"),
    "ko": LanguageInfo("ko", "Korean", "한국어"),
    "es": LanguageInfo("es", "Spanish", "Español"),
    "fr": LanguageInfo("fr", "French", "Français"),
    "de": LanguageInfo("de", "German", "Deutsch"),
    "pt": LanguageInfo("pt", "Portuguese", "Português"),
    "ru": LanguageInfo("ru", "Russian", "Русский"),
    "ar": LanguageInfo("ar", "Arabic", "العربية", "rtl"),
    "hi": LanguageInfo("hi", "Hindi", "हिन्दी"),
}


@dataclass
class TranslationEntry:
    """翻译条目"""
    key: str
    value: str
    context: str = ""
    plural_form: Optional[str] = None  # 复数形式


@dataclass
class Locale:
    """本地化数据"""
    language: Language
    translations: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get(self, key: str, default: Optional[str] = None) -> str:
        """获取翻译"""
        return self.translations.get(key, default or key)
    
    def set(self, key: str, value: str) -> None:
        """设置翻译"""
        self.translations[key] = value
    
    def merge(self, other: 'Locale') -> None:
        """合并翻译"""
        self.translations.update(other.translations)


@dataclass
class TranslationStats:
    """翻译统计"""
    total_keys: int = 0
    translated_keys: int = 0
    missing_keys: List[str] = field(default_factory=list)
    completion_rate: float = 0.0


class TranslationCache:
    """翻译缓存"""
    
    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, str] = {}
        self._max_size = max_size
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[str]:
        """获取缓存"""
        with self._lock:
            value = self._cache.get(key)
            if value:
                self._hits += 1
            else:
                self._misses += 1
            return value
    
    def set(self, key: str, value: str) -> None:
        """设置缓存"""
        with self._lock:
            if len(self._cache) >= self._max_size:
                # 简单驱逐策略：清除最旧的
                first_key = next(iter(self._cache))
                del self._cache[first_key]
            self._cache[key] = value
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0


class LanguageManager:
    """
    多语言管理器
    
    核心功能：
    - 多语言支持
    - 本地化数据管理
    - 翻译缓存
    - 动态语言切换
    - 复数形式支持
    - 占位符替换
    """
    
    def __init__(self, default_language: Language = Language.ZH_CN):
        """
        初始化管理器
        
        Args:
            default_language: 默认语言
        """
        self._default_language = default_language
        self._current_language = default_language
        
        # 本地化数据
        self._locales: Dict[Language, Locale] = {}
        
        # 缓存
        self._cache = TranslationCache()
        
        # 翻译来源
        self._sources: List[str] = []
        
        # 事件回调
        self._on_language_change: List[Callable] = []
        
        # 锁
        self._lock = threading.RLock()
        
        # 加载内置翻译
        self._load_builtin_translations()
    
    def _load_builtin_translations(self) -> None:
        """加载内置翻译"""
        # 内置的中文翻译
        builtin_zh = {
            "app.name": "LivingTreeAI",
            "app.slogan": "构建AI编程的未来",
            "menu.file": "文件",
            "menu.edit": "编辑",
            "menu.view": "视图",
            "menu.help": "帮助",
            "button.save": "保存",
            "button.cancel": "取消",
            "button.confirm": "确认",
            "button.delete": "删除",
            "button.edit": "编辑",
            "button.add": "添加",
            "button.search": "搜索",
            "button.export": "导出",
            "button.import": "导入",
            "status.ready": "就绪",
            "status.loading": "加载中...",
            "status.saving": "保存中...",
            "status.error": "错误",
            "status.success": "成功",
            "error.not_found": "未找到",
            "error.permission": "权限不足",
            "error.network": "网络错误",
            "error.timeout": "请求超时",
            "confirm.delete": "确定要删除吗？",
            "confirm.exit": "确定要退出吗？",
        }
        
        builtin_en = {
            "app.name": "LivingTreeAI",
            "app.slogan": "Build the Future of AI Coding",
            "menu.file": "File",
            "menu.edit": "Edit",
            "menu.view": "View",
            "menu.help": "Help",
            "button.save": "Save",
            "button.cancel": "Cancel",
            "button.confirm": "Confirm",
            "button.delete": "Delete",
            "button.edit": "Edit",
            "button.add": "Add",
            "button.search": "Search",
            "button.export": "Export",
            "button.import": "Import",
            "status.ready": "Ready",
            "status.loading": "Loading...",
            "status.saving": "Saving...",
            "status.error": "Error",
            "status.success": "Success",
            "error.not_found": "Not Found",
            "error.permission": "Permission Denied",
            "error.network": "Network Error",
            "error.timeout": "Request Timeout",
            "confirm.delete": "Are you sure you want to delete?",
            "confirm.exit": "Are you sure you want to exit?",
        }
        
        # 创建 Locale 对象
        zh_locale = Locale(Language.ZH_CN, builtin_zh)
        en_locale = Locale(Language.EN, builtin_en)
        
        self._locales[Language.ZH_CN] = zh_locale
        self._locales[Language.EN] = en_locale
    
    def add_source(self, source: str) -> None:
        """
        添加翻译源
        
        Args:
            source: 翻译源路径
        """
        with self._lock:
            if source not in self._sources:
                self._sources.append(source)
                self._load_source(source)
    
    def _load_source(self, source: str) -> None:
        """加载翻译源"""
        if not os.path.exists(source):
            return
        
        try:
            if source.endswith('.json'):
                self._load_json_source(source)
            elif source.endswith('.yaml') or source.endswith('.yml'):
                self._load_yaml_source(source)
        except Exception:
            pass
    
    def _load_json_source(self, source: str) -> None:
        """加载 JSON 翻译源"""
        with open(source, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for lang_code, translations in data.items():
            try:
                lang = Language(lang_code)
            except ValueError:
                continue
            
            if lang not in self._locales:
                self._locales[lang] = Locale(lang)
            
            self._locales[lang].merge(Locale(lang, translations))
    
    def _load_yaml_source(self, source: str) -> None:
        """加载 YAML 翻译源"""
        try:
            import yaml
            with open(source, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            for lang_code, translations in data.items():
                try:
                    lang = Language(lang_code)
                except ValueError:
                    continue
                
                if lang not in self._locales:
                    self._locales[lang] = Locale(lang)
                
                self._locales[lang].merge(Locale(lang, translations))
        except ImportError:
            pass
    
    def set_language(self, language: Language) -> None:
        """
        设置当前语言
        
        Args:
            language: 语言
        """
        with self._lock:
            if language != self._current_language:
                self._current_language = language
                self._cache.clear()  # 清空缓存
                
                # 触发事件
                for callback in self._on_language_change:
                    try:
                        callback(language)
                    except Exception:
                        pass
    
    def get_language(self) -> Language:
        """获取当前语言"""
        return self._current_language
    
    def t(
        self,
        key: str,
        default: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """
        翻译文本
        
        Args:
            key: 翻译键
            default: 默认文本
            **kwargs: 占位符参数
            
        Returns:
            翻译后的文本
        """
        # 检查缓存
        cache_key = f"{self._current_language.value}:{key}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return self._format(cached, kwargs)
        
        # 获取翻译
        locale = self._locales.get(self._current_language)
        if not locale:
            return default or key
        
        value = locale.get(key, default or key)
        
        # 缓存结果
        self._cache.set(cache_key, value)
        
        return self._format(value, kwargs)
    
    def _format(self, text: str, kwargs: Dict[str, Any]) -> str:
        """格式化文本"""
        if not kwargs:
            return text
        
        # 支持 {name} 和 {{name}} 格式
        for key, value in kwargs.items():
            text = text.replace(f"{{{key}}}", str(value))
            text = text.replace(f"{{{{{key}}}}}", str(value))
        
        return text
    
    def tn(
        self,
        singular: str,
        plural: str,
        count: int,
        **kwargs: Any
    ) -> str:
        """
        复数形式翻译
        
        Args:
            singular: 单数形式
            plural: 复数形式
            count: 数量
            **kwargs: 其他参数
            
        Returns:
            翻译后的文本
        """
        # 简化实现：英语规则
        if count == 1:
            return self.t(singular, **kwargs)
        else:
            return self.t(plural, **kwargs)
    
    def get_available_languages(self) -> List[Language]:
        """获取可用语言列表"""
        return list(self._locales.keys())
    
    def get_language_info(self, language: Language) -> Optional[LanguageInfo]:
        """获取语言信息"""
        return LANGUAGE_INFO.get(language.value)
    
    def get_translation_stats(self, language: Language) -> TranslationStats:
        """
        获取翻译统计
        
        Args:
            language: 语言
            
        Returns:
            翻译统计
        """
        # 获取基准翻译（英语）
        base_locale = self._locales.get(Language.EN)
        if not base_locale:
            return TranslationStats()
        
        target_locale = self._locales.get(language)
        
        total_keys = len(base_locale.translations)
        translated_keys = 0
        missing_keys = []
        
        for key in base_locale.translations:
            if target_locale and key in target_locale.translations:
                translated_keys += 1
            else:
                missing_keys.append(key)
        
        completion_rate = (translated_keys / total_keys * 100) if total_keys > 0 else 0
        
        return TranslationStats(
            total_keys=total_keys,
            translated_keys=translated_keys,
            missing_keys=missing_keys,
            completion_rate=completion_rate,
        )
    
    def export_locale(self, language: Language) -> str:
        """
        导出本地化数据
        
        Args:
            language: 语言
            
        Returns:
            JSON 格式数据
        """
        locale = self._locales.get(language)
        if not locale:
            return "{}"
        
        return json.dumps(locale.translations, indent=2, ensure_ascii=False)
    
    def import_locale(self, language: Language, json_str: str) -> bool:
        """
        导入本地化数据
        
        Args:
            language: 语言
            json_str: JSON 字符串
            
        Returns:
            是否成功
        """
        try:
            translations = json.loads(json_str)
            
            if language not in self._locales:
                self._locales[language] = Locale(language)
            
            self._locales[language].merge(Locale(language, translations))
            return True
        except Exception:
            return False
    
    def on_language_change(self, callback: Callable) -> None:
        """注册语言切换事件"""
        self._on_language_change.append(callback)
    
    def __call__(self, key: str, **kwargs: Any) -> str:
        """便捷调用"""
        return self.t(key, **kwargs)


# 全局实例
_global_manager: Optional[LanguageManager] = None
_manager_lock = threading.Lock()


def get_language_manager() -> LanguageManager:
    """获取全局语言管理器"""
    global _global_manager
    
    with _manager_lock:
        if _global_manager is None:
            _global_manager = LanguageManager()
        return _global_manager


# 便捷函数
def t(key: str, **kwargs: Any) -> str:
    """翻译文本"""
    return get_language_manager().t(key, **kwargs)


def set_language(language: Language) -> None:
    """设置语言"""
    get_language_manager().set_language(language)


def get_language() -> Language:
    """获取当前语言"""
    return get_language_manager().get_language()
