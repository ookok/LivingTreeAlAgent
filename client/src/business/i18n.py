"""
国际化与本地化系统 - LivingTreeAI

支持多语言：中文(zh_CN)、英文(en_US)
支持跨平台：Windows、macOS、Linux

使用示例：
    from business.i18n import i18n, set_locale, get_available_locales

    # 翻译字符串
    print(i18n._("Hello World"))  # 你好世界

    # 切换语言
    set_locale("en_US")
    print(i18n._("Hello World"))  # Hello World

    # 获取可用语言
    print(get_available_locales())  # {"zh_CN": "简体中文", "en_US": "English"}
"""

import os
import gettext as _gettext
import locale as _locale
from pathlib import Path
from typing import Dict, Optional, Callable
from dataclasses import dataclass


# ============================================================================
# 配置
# ============================================================================

# 翻译文件目录
LOCALE_DIR = Path(__file__).parent.parent / "locales"

# 支持的语言
SUPPORTED_LOCALES = {
    "zh_CN": "简体中文",
    "en_US": "English",
    "zh_TW": "繁體中文",
    "ja_JP": "日本語",
}

# 默认语言
DEFAULT_LOCALE = "zh_CN"


# ============================================================================
# i18n 管理器
# ============================================================================

class I18nManager:
    """
    国际化管理器

    使用 GNU gettext 进行翻译，支持：
    - 单数翻译：i18n._("Hello")
    - 复数翻译：i18n.ngettext("apple", "apples", n)
    - 占位符翻译：i18n._("Hello {name}").format(name="World")
    """

    _instances: Dict[str, "I18nManager"] = {}

    def __init__(self, domain: str = "messages"):
        self.domain = domain
        self._current_locale = DEFAULT_LOCALE
        self._translation: Optional[_gettext.NullTranslations] = None
        self._translations: Dict[str, _gettext.GNUTranslations] = {}

    @classmethod
    def get_instance(cls, domain: str = "messages") -> "I18nManager":
        """获取单例实例"""
        if domain not in cls._instances:
            cls._instances[domain] = cls(domain)
        return cls._instances[domain]

    def set_locale(self, locale: str) -> bool:
        """
        设置当前语言

        Args:
            locale: 语言代码 (如 "zh_CN", "en_US")

        Returns:
            bool: 是否设置成功
        """
        if locale not in SUPPORTED_LOCALES:
            locale = DEFAULT_LOCALE

        self._current_locale = locale

        # 尝试加载翻译
        try:
            self._translation = _gettext.translation(
                self.domain,
                localedir=str(LOCALE_DIR),
                languages=[locale],
            )
        except FileNotFoundError:
            # 回退到 NullTranslations
            self._translation = _gettext.NullTranslations()

        self._translations[locale] = self._translation
        return True

    def get_locale(self) -> str:
        """获取当前语言"""
        return self._current_locale

    def _(self, message: str, **kwargs) -> str:
        """
        翻译字符串

        Args:
            message: 要翻译的字符串
            **kwargs: 占位符参数

        Returns:
            str: 翻译后的字符串
        """
        if self._translation:
            translated = self._translation.gettext(message)
        else:
            translated = message

        # 处理占位符
        if kwargs:
            try:
                translated = translated.format(**kwargs)
            except (KeyError, ValueError):
                pass

        return translated

    def ngettext(self, singular: str, plural: str, n: int) -> str:
        """
        复数形式翻译

        Args:
            singular: 单数形式
            plural: 复数形式
            n: 数量

        Returns:
            str: 翻译后的字符串
        """
        if self._translation:
            return self._translation.ngettext(singular, plural, n)
        return singular if n == 1 else plural

    def get_available_locales(self) -> Dict[str, str]:
        """获取支持的语言列表"""
        return SUPPORTED_LOCALES.copy()

    def install(self) -> Callable[[str], str]:
        """
        安装到全局命名空间

        Returns:
            callable: 翻译函数
        """
        import builtins
        builtins.__dict__["_"] = self._
        builtins.__dict__["ngettext"] = self.ngettext
        return self._


# ============================================================================
# 全局实例和便捷函数
# ============================================================================

# 全局 i18n 实例
_i18n: Optional[I18nManager] = None


def get_i18n() -> I18nManager:
    """获取全局 i18n 实例"""
    global _i18n
    if _i18n is None:
        _i18n = I18nManager.get_instance()
        # 尝试自动检测系统语言
        auto_detect_locale()
    return _i18n


def set_locale(locale: str) -> bool:
    """
    设置全局语言

    Args:
        locale: 语言代码

    Returns:
        bool: 是否设置成功
    """
    return get_i18n().set_locale(locale)


def get_locale() -> str:
    """获取当前语言"""
    return get_i18n().get_locale()


def get_available_locales() -> Dict[str, str]:
    """获取支持的语言列表"""
    return get_i18n().get_available_locales()


def auto_detect_locale() -> str:
    """
    自动检测系统语言

    Returns:
        str: 检测到的语言代码
    """
    # 1. 尝试环境变量
    env_locale = os.environ.get("HERMES_LOCALE") or os.environ.get("LANG")
    if env_locale:
        # 提取语言部分 (如 "zh_CN.UTF-8" -> "zh_CN")
        lang = env_locale.split(".")[0].replace("-", "_")
        if lang in SUPPORTED_LOCALES:
            get_i18n().set_locale(lang)
            return lang

    # 2. 尝试系统 locale
    try:
        system_locale = _locale.getdefaultlocale()[0]
        if system_locale:
            lang = system_locale.replace("-", "_")
            if lang in SUPPORTED_LOCALES:
                get_i18n().set_locale(lang)
                return lang
            # 尝试匹配主语言 (如 "zh_TW" -> "zh_CN")
            primary = lang.split("_")[0]
            for supported in SUPPORTED_LOCALES:
                if supported.startswith(primary):
                    get_i18n().set_locale(supported)
                    return supported
    except Exception:
        pass

    # 3. 默认值
    get_i18n().set_locale(DEFAULT_LOCALE)
    return DEFAULT_LOCALE


# 便捷函数
def _(message: str, **kwargs) -> str:
    """翻译字符串"""
    return get_i18n()._(message, **kwargs)


def ngettext(singular: str, plural: str, n: int) -> str:
    """复数形式翻译"""
    return get_i18n().ngettext(singular, plural, n)


# ============================================================================
# API 响应翻译 (用于 FastAPI)
# ============================================================================

@dataclass
class APIResponse:
    """支持多语言的 API 响应"""
    code: int
    message: str
    data: Optional[Dict] = None

    @classmethod
    def success(cls, message: str = None, data: Dict = None) -> "APIResponse":
        """成功响应"""
        msg = message or _("Success")
        return cls(code=0, message=msg, data=data)

    @classmethod
    def error(cls, message: str, code: int = -1) -> "APIResponse":
        """错误响应"""
        return cls(code=code, message=message)


# ============================================================================
# 初始化
# ============================================================================

def _init_i18n():
    """初始化 i18n 系统"""
    # 确保 locale 目录存在
    LOCALE_DIR.mkdir(parents=True, exist_ok=True)
    # 自动检测并设置语言
    auto_detect_locale()


# 模块加载时自动初始化
_init_i18n()
