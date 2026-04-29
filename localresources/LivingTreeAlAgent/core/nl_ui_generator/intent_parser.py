"""
Intent Parser - 自然语言意图理解引擎
====================================

将用户的自然语言描述解析为结构化的意图对象。

支持的意图类型:
    - add_element: 添加UI元素
    - modify_element: 修改UI元素
    - move_element: 移动UI元素
    - delete_element: 删除UI元素
    - bind_action: 绑定动作
    - change_style: 改变样式
    - create_panel: 创建面板
"""

import re
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import asyncio
import json


class IntentType(Enum):
    """意图类型枚举"""
    # UI元素操作
    ADD_ELEMENT = "add_element"           # 添加元素
    MODIFY_ELEMENT = "modify_element"     # 修改元素
    MOVE_ELEMENT = "move_element"         # 移动元素
    DELETE_ELEMENT = "delete_element"     # 删除元素
    RESIZE_ELEMENT = "resize_element"     # 调整大小

    # 样式操作
    CHANGE_STYLE = "change_style"         # 改变样式
    CHANGE_COLOR = "change_color"          # 改变颜色
    CHANGE_SIZE = "change_size"           # 改变尺寸

    # 动作绑定
    BIND_ACTION = "bind_action"           # 绑定动作
    UNBIND_ACTION = "unbind_action"       # 解绑动作
    AUTO_ACTION = "auto_action"           # 自动执行

    # 面板操作
    CREATE_PANEL = "create_panel"         # 创建面板
    MODIFY_PANEL = "modify_panel"         # 修改面板
    DELETE_PANEL = "delete_panel"         # 删除面板

    # 数据绑定
    BIND_DATA = "bind_data"               # 绑定数据
    LIVE_UPDATE = "live_update"            # 实时更新

    # 查询
    QUERY_UI = "query_ui"                 # 查询UI状态
    QUERY_HISTORY = "query_history"      # 查询历史

    # 撤销/重做
    UNDO = "undo"                        # 撤销
    REDO = "redo"                         # 重做

    # 未知
    UNKNOWN = "unknown"                   # 未知意图


@dataclass
class IntentPattern:
    """意图模式定义"""
    type: IntentType
    patterns: list  # 正则表达式列表
    param_extractors: dict  # 参数提取器


@dataclass
class Intent:
    """解析后的意图对象"""
    type: IntentType
    params: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    confidence: float = 1.0
    original_text: str = ""
    suggested_actions: list = field(default_factory=list)


class IntentParser:
    """自然语言意图解析器"""

    # 内置意图模式
    DEFAULT_PATTERNS = [
        # 添加元素
        IntentPattern(
            type=IntentType.ADD_ELEMENT,
            patterns=[
                r"在(.+?)添加(.+?)",
                r"给(.+?)加一个(.+?)",
                r"给(.+?)添加(.+?)",
                r"新增(.+?)到(.+?)",
                r"放一个(.+?)在(.+?)",
            ],
            param_extractors={
                "target": 1,
                "element": 2,
            }
        ),

        # 移动元素
        IntentPattern(
            type=IntentType.MOVE_ELEMENT,
            patterns=[
                r"把(.+?)移动到(.+?)",
                r"将(.+?)移到(.+?)",
                r"把(.+?)放到(.+?)",
                r"调整(.+?)位置",
            ],
            param_extractors={
                "element": 1,
                "position": 2,
            }
        ),

        # 调整大小
        IntentPattern(
            type=IntentType.RESIZE_ELEMENT,
            patterns=[
                r"调整(.+?)的大小",
                r"把(.+?)变大?",
                r"把(.+?)变小?",
                r"设置(.+?)尺寸",
            ],
            param_extractors={
                "element": 1,
            }
        ),

        # 改变颜色
        IntentPattern(
            type=IntentType.CHANGE_COLOR,
            patterns=[
                r"改变(.+?)的颜色",
                r"把(.+?)变成(.+?)色",
                r"设置(.+?)为(.+?)",
            ],
            param_extractors={
                "element": 1,
                "color": 2,
            }
        ),

        # 绑定动作
        IntentPattern(
            type=IntentType.BIND_ACTION,
            patterns=[
                r"点击(.+?)时(.+?)",
                r"当(.+?)时执行(.+?)",
                r"(.+?)触发(.+?)",
                r"(.+?)调用(.+?)",
            ],
            param_extractors={
                "element": 1,
                "action": 2,
            }
        ),

        # 创建面板
        IntentPattern(
            type=IntentType.CREATE_PANEL,
            patterns=[
                r"创建一个(.+?)面板",
                r"新建(.+?)面板",
                r"添加(.+?)面板",
            ],
            param_extractors={
                "panel_type": 1,
            }
        ),

        # 数据绑定
        IntentPattern(
            type=IntentType.BIND_DATA,
            patterns=[
                r"显示(.+?)的(.+?)",
                r"把(.+?)绑定到(.+?)",
            ],
            param_extractors={
                "data_source": 1,
                "target": 2,
            }
        ),

        # 实时更新
        IntentPattern(
            type=IntentType.LIVE_UPDATE,
            patterns=[
                r"实时更新(.+?)",
                r"自动刷新(.+?)",
                r"监控(.+?)",
            ],
            param_extractors={
                "target": 1,
            }
        ),

        # 撤销
        IntentPattern(
            type=IntentType.UNDO,
            patterns=[
                r"撤销",
                r"取消上一步",
                r"回退",
            ],
            param_extractors={}
        ),

        # 重做
        IntentPattern(
            type=IntentType.REDO,
            patterns=[
                r"重做",
                r"恢复",
                r"再来一次",
            ],
            param_extractors={}
        ),

        # 查询UI
        IntentPattern(
            type=IntentType.QUERY_UI,
            patterns=[
                r"当前有哪些(.+?)",
                r"查看(.+?)状态",
                r"显示(.+?)列表",
            ],
            param_extractors={
                "query_type": 1,
            }
        ),
    ]

    def __init__(self):
        self.patterns: list[IntentPattern] = []
        self.custom_patterns: list[IntentPattern] = []
        self.intent_history: list[Intent] = []
        self._load_builtin_patterns()

    def _load_builtin_patterns(self):
        """加载内置模式"""
        self.patterns = self.DEFAULT_PATTERNS.copy()

    def register_pattern(self, pattern: IntentPattern):
        """注册自定义模式"""
        self.custom_patterns.append(pattern)

    def parse(self, text: str) -> Intent:
        """
        解析自然语言文本为意图

        Args:
            text: 用户输入的自然语言文本

        Returns:
            Intent: 解析后的意图对象
        """
        text = text.strip()
        if not text:
            return Intent(
                type=IntentType.UNKNOWN,
                original_text=text,
                confidence=0.0
            )

        # 尝试匹配所有模式
        for pattern in self.patterns + self.custom_patterns:
            intent = self._try_match_pattern(text, pattern)
            if intent and intent.confidence > 0.5:
                self.intent_history.append(intent)
                return intent

        # 无法识别，返回UNKNOWN
        return Intent(
            type=IntentType.UNKNOWN,
            original_text=text,
            confidence=0.0,
            suggested_actions=self._suggest_alternatives(text)
        )

    async def parse_async(self, text: str) -> Intent:
        """异步解析"""
        return await asyncio.to_thread(self.parse, text)

    def _try_match_pattern(self, text: str, pattern: IntentPattern) -> Optional[Intent]:
        """尝试匹配单个模式"""
        for regex_pattern in pattern.patterns:
            match = re.search(regex_pattern, text)
            if match:
                groups = match.groups()

                # 提取参数
                params = {}
                for key, idx in pattern.param_extractors.items():
                    if idx <= len(groups):
                        value = groups[idx - 1]
                        if value:
                            params[key] = value.strip()

                # 计算置信度
                confidence = self._calculate_confidence(text, pattern, match)

                return Intent(
                    type=pattern.type,
                    params=params,
                    original_text=text,
                    confidence=confidence,
                    suggested_actions=self._get_suggested_actions(pattern.type, params)
                )

        return None

    def _calculate_confidence(self, text: str, pattern: IntentPattern, match: re.Match) -> float:
        """计算匹配置信度"""
        base_confidence = 0.8

        # 完全匹配（无多余文字）
        if match.start() == 0 and match.end() == len(text):
            base_confidence += 0.1

        # 有足够的捕获组
        non_empty_groups = sum(1 for g in match.groups() if g)
        if non_empty_groups >= 2:
            base_confidence += 0.05

        # 包含明确的动作词
        action_words = ["添加", "创建", "删除", "移动", "改变", "设置", "绑定"]
        for word in action_words:
            if word in text:
                base_confidence += 0.02

        return min(base_confidence, 1.0)

    def _get_suggested_actions(self, intent_type: IntentType, params: dict) -> list:
        """获取建议的后续操作"""
        suggestions = []

        if intent_type == IntentType.ADD_ELEMENT:
            suggestions.append({
                "action": "confirm_element",
                "label": "确认添加",
                "params": params
            })
            suggestions.append({
                "action": "modify_position",
                "label": "调整位置",
                "params": params
            })

        elif intent_type == IntentType.BIND_ACTION:
            suggestions.append({
                "action": "search_action",
                "label": "搜索动作",
                "params": params
            })
            suggestions.append({
                "action": "create_action",
                "label": "创建新动作",
                "params": params
            })

        elif intent_type == IntentType.CHANGE_COLOR:
            suggestions.append({
                "action": "preview_color",
                "label": "预览颜色",
                "params": params
            })

        return suggestions

    def _suggest_alternatives(self, text: str) -> list:
        """当无法识别时，给出替代建议"""
        suggestions = []

        # 根据关键词推荐
        keywords = {
            "按钮": ["添加按钮", "修改按钮样式"],
            "面板": ["创建面板", "调整面板布局"],
            "颜色": ["改变颜色", "调整配色"],
            "位置": ["移动元素", "调整位置"],
            "功能": ["绑定动作", "创建新功能"],
        }

        for key, values in keywords.items():
            if key in text:
                suggestions.extend(values)

        return list(set(suggestions))[:5]

    def learn_from_feedback(self, text: str, corrected_intent: Intent):
        """
        从用户反馈中学习

        当用户的纠正被采纳时，将新的表达模式添加到模式库
        """
        # 分析新表达与纠正后意图的映射关系
        new_pattern = IntentPattern(
            type=corrected_intent.type,
            patterns=[re.escape(text)],  # 精确匹配
            param_extractors=corrected_intent.params
        )
        self.custom_patterns.append(new_pattern)


# 全局单例
_parser_instance: Optional[IntentParser] = None


def get_intent_parser() -> IntentParser:
    """获取意图解析器单例"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = IntentParser()
    return _parser_instance