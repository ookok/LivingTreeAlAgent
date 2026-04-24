"""
意图检测器 - 识别用户从外部应用发起的请求意图
==============================================

支持的应用类型：
- word / wps    - 文档处理
- excel / wps表格 - 数据分析
- outlook / 邮件 - 邮件处理
- browser - 浏览器
- terminal - 终端
- general - 通用查询
"""

from enum import Enum
from typing import Optional, Dict, Any
import re


class AppType(Enum):
    """应用类型"""
    WORD = "word"           # Microsoft Word
    WPS = "wps"             # WPS Office
    EXCEL = "excel"         # Microsoft Excel
    WPS_SPREADSHEET = "wps_spreadsheet"  # WPS 表格
    OUTLOOK = "outlook"     # Outlook 邮件
    BROWSER = "browser"     # 浏览器
    TERMINAL = "terminal"   # 终端
    NOTEPAD = "notepad"     # 记事本
    GENERAL = "general"     # 通用


class IntentType(Enum):
    """意图类型"""
    QUERY_KNOWLEDGE = "query_knowledge"       # 知识库查询
    SUMMARIZE = "summarize"                   # 总结摘要
    TRANSLATE = "translate"                   # 翻译
    POLISH = "polish"                         # 润色改写
    CORRECT = "correct"                       # 错别字纠正
    ANALYZE = "analyze"                       # 分析
    EXTRACT = "extract"                       # 提取信息
    GENERATE = "generate"                     # 生成内容
    SEARCH = "search"                          # 搜索
    ANSWER = "answer"                          # 问答


class IntentDetector:
    """
    智能意图检测器

    根据上下文和文本内容判断用户意图
    """

    # 关键词映射
    INTENT_KEYWORDS = {
        IntentType.QUERY_KNOWLEDGE: [
            "查一下", "查询", "搜索", "知识库", "有没有",
            "什么是", "什么叫", "定义", "概念"
        ],
        IntentType.SUMMARIZE: [
            "总结", "概括", "摘要", "要点", "提炼",
            "主要说了什么", "核心内容"
        ],
        IntentType.TRANSLATE: [
            "翻译", "英文", "中文", "日文", "译成",
            "translate", "翻译成"
        ],
        IntentType.POLISH: [
            "润色", "改写", "优化", "优化一下", "写得好一点",
            "更专业", "书面语"
        ],
        IntentType.CORRECT: [
            "错别字", "纠正", "修正", "检查错误",
            "语法错误", "拼写"
        ],
        IntentType.ANALYZE: [
            "分析", "解读", "评估", "对比",
            "优缺点", "利弊", "风险"
        ],
        IntentType.EXTRACT: [
            "提取", "抽取", "列出", "找出来",
            "关键词", "人名", "日期", "数字"
        ],
        IntentType.GENERATE: [
            "生成", "写", "创建", "帮我写",
            "起草", "拟一份"
        ],
        IntentType.SEARCH: [
            "搜索", "查找", "google", "百度",
            "网上", "相关信息"
        ],
    }

    # 应用类型识别
    APP_PATTERNS = {
        AppType.WORD: [
            r"\.docx?$", r"\.docm?$",
            r"microsoft\s*word", r"winword\.exe"
        ],
        AppType.WPS: [
            r"wps", r"et\.exe", r"wpp\.exe",
            r"kingsoft", r"金山文档"
        ],
        AppType.EXCEL: [
            r"\.xlsx?$", r"\.xlsm?$",
            r"excel\.exe", r"et\.exe"
        ],
        AppType.OUTLOOK: [
            r"outlook\.exe", r"邮箱", r"邮件",
            r"subject:", r"收件人"
        ],
        AppType.BROWSER: [
            r"chrome\.exe", r"firefox\.exe",
            r"edge\.exe", r"browser"
        ],
        AppType.TERMINAL: [
            r"powershell\.exe", r"cmd\.exe",
            r"terminal", r"bash", r"zsh"
        ],
    }

    def __init__(self):
        self._app_patterns = {
            app: [re.compile(p, re.I) for p in patterns]
            for app, patterns in self.APP_PATTERNS.items()
        }

    def detect_app_type(self, context: Optional[str] = None) -> AppType:
        """检测应用类型"""
        if not context:
            return AppType.GENERAL

        for app, patterns in self._app_patterns.items():
            for pattern in patterns:
                if pattern.search(context):
                    return app

        return AppType.GENERAL

    def detect_intent(self, text: str, context: Optional[str] = None) -> IntentType:
        """
        检测用户意图

        Args:
            text: 用户输入的文本
            context: 上下文（如应用类型、前文等）

        Returns:
            IntentType: 检测到的意图类型
        """
        text_lower = text.lower()

        # 优先检测明确意图
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return intent

        # 基于应用类型的默认意图
        if context:
            app_type = self.detect_app_type(context)
            default_intents = {
                AppType.WORD: IntentType.QUERY_KNOWLEDGE,
                AppType.WPS: IntentType.QUERY_KNOWLEDGE,
                AppType.EXCEL: IntentType.ANALYZE,
                AppType.OUTLOOK: IntentType.SUMMARIZE,
                AppType.BROWSER: IntentType.SEARCH,
                AppType.GENERAL: IntentType.ANSWER,
            }
            return default_intents.get(app_type, IntentType.ANSWER)

        return IntentType.ANSWER

    def build_request(
        self,
        text: str,
        context: Optional[str] = None,
        user_intent: Optional[IntentType] = None
    ) -> Dict[str, Any]:
        """
        构建标准化的外部请求

        Args:
            text: 用户输入
            context: 上下文信息
            user_intent: 用户指定的意图（可选）

        Returns:
            Dict: 标准化的请求对象
        """
        app_type = self.detect_app_type(context)
        intent = user_intent or self.detect_intent(text, context)

        return {
            "text": text,
            "context": context,
            "app_type": app_type.value,
            "intent": intent.value,
            "metadata": {
                "source": "external_integration",
                "timestamp": None,  # 填充时间戳
            }
        }


# 全局实例
_detector = None


def get_intent_detector() -> IntentDetector:
    """获取意图检测器单例"""
    global _detector
    if _detector is None:
        _detector = IntentDetector()
    return _detector


def quick_detect(text: str, context: Optional[str] = None) -> Dict[str, Any]:
    """
    快速意图检测

    使用示例:
        >>> result = quick_detect("查一下公司章程", "word")
        >>> print(result['intent'])  # 'query_knowledge'
    """
    return get_intent_detector().build_request(text, context)
