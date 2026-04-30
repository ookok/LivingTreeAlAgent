"""国际化服务 - 支持多语言切换"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Dict, Any

class I18nService(QObject):
    """国际化服务"""
    
    locale_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._locales = {
            'zh-CN': self._load_chinese_locale(),
            'en-US': self._load_english_locale(),
        }
        self._current_locale = 'zh-CN'
    
    def _load_chinese_locale(self) -> Dict[str, str]:
        """加载中文语言包"""
        return {
            'welcome': '欢迎使用 AI Agent',
            'send': '发送',
            'clear': '清空',
            'settings': '设置',
            'help': '帮助',
            'search': '搜索',
            'create': '创建',
            'analyze': '分析',
            'learn': '学习',
            'code': '代码',
            'file': '文件',
            'message': '消息',
            'history': '历史',
            'topic': '主题',
            'action': '操作',
            'recommendation': '推荐',
            'confidence': '置信度',
            'source': '来源',
            'running': '运行中...',
            'completed': '完成',
            'error': '错误',
            'warning': '警告',
            'success': '成功',
            'typing': '正在输入...',
            'thinking': '正在思考...',
            'suggestion': '建议',
            'apply': '应用',
            'copy': '复制',
            'explain': '解释',
            'run': '运行',
            'save': '保存',
            'format': '格式化',
            'comment': '注释',
            'theme': '主题',
            'language': '语言',
            'dark': '暗色',
            'light': '亮色',
            'system': '系统',
        }
    
    def _load_english_locale(self) -> Dict[str, str]:
        """加载英文语言包"""
        return {
            'welcome': 'Welcome to AI Agent',
            'send': 'Send',
            'clear': 'Clear',
            'settings': 'Settings',
            'help': 'Help',
            'search': 'Search',
            'create': 'Create',
            'analyze': 'Analyze',
            'learn': 'Learn',
            'code': 'Code',
            'file': 'File',
            'message': 'Message',
            'history': 'History',
            'topic': 'Topic',
            'action': 'Action',
            'recommendation': 'Recommendation',
            'confidence': 'Confidence',
            'source': 'Source',
            'running': 'Running...',
            'completed': 'Completed',
            'error': 'Error',
            'warning': 'Warning',
            'success': 'Success',
            'typing': 'Typing...',
            'thinking': 'Thinking...',
            'suggestion': 'Suggestion',
            'apply': 'Apply',
            'copy': 'Copy',
            'explain': 'Explain',
            'run': 'Run',
            'save': 'Save',
            'format': 'Format',
            'comment': 'Comment',
            'theme': 'Theme',
            'language': 'Language',
            'dark': 'Dark',
            'light': 'Light',
            'system': 'System',
        }
    
    def set_locale(self, locale: str):
        """设置语言"""
        if locale in self._locales:
            self._current_locale = locale
            self.locale_changed.emit(locale)
    
    def translate(self, key: str, params: Dict[str, Any] = None) -> str:
        """翻译文本"""
        template = self._locales[self._current_locale].get(key, key)
        
        if params:
            try:
                return template.format(**params)
            except (KeyError, ValueError):
                return template
        
        return template
    
    def get_current_locale(self) -> str:
        """获取当前语言"""
        return self._current_locale
    
    def get_available_locales(self) -> list:
        """获取可用语言列表"""
        return list(self._locales.keys())
    
    def add_locale(self, locale: str, translations: Dict[str, str]):
        """添加新语言"""
        self._locales[locale] = translations

_i18n_service = None

def get_i18n_service() -> I18nService:
    """获取国际化服务实例"""
    global _i18n_service
    if _i18n_service is None:
        _i18n_service = I18nService()
    return _i18n_service