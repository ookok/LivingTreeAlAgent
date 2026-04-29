"""
Action Repository - 动作仓库
=============================

管理和存储所有可用的UI动作，支持自然语言搜索和动态注册。

动作定义:
    {
        "id": "action_id",
        "name": "动作名称",
        "description": "动作描述",
        "handler": "module.function",
        "params": [...],
        "return_type": "void|string|boolean|object",
        "category": "route|network|ai|system",
        "keywords": ["关键词1", "关键词2"],
    }
"""

import json
import re
import asyncio
from typing import Optional, Callable, Any, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


class ActionCategory(Enum):
    """动作分类"""
    ROUTE = "route"          # 路由相关
    NETWORK = "network"     # 网络相关
    AI = "ai"               # AI相关
    SYSTEM = "system"       # 系统相关
    DATA = "data"           # 数据相关
    UI = "ui"               # UI相关
    CUSTOM = "custom"       # 自定义


class ReturnType(Enum):
    """返回值类型"""
    VOID = "void"           # 无返回值
    STRING = "string"       # 字符串
    BOOLEAN = "boolean"     # 布尔值
    NUMBER = "number"       # 数字
    OBJECT = "object"       # 对象
    ARRAY = "array"         # 数组


@dataclass
class ActionParameter:
    """动作参数定义"""
    name: str
    type: str  # string, number, boolean, object, array
    description: str = ""
    required: bool = True
    default: Any = None
    options: list = None  # 可选值列表


@dataclass
class Action:
    """动作定义"""
    id: str
    name: str
    description: str
    handler: str  # "module.function" 格式

    # 参数和返回值
    params: list[ActionParameter] = field(default_factory=list)
    return_type: ReturnType = ReturnType.VOID

    # 分类和标签
    category: ActionCategory = ActionCategory.CUSTOM
    keywords: list[str] = field(default_factory=list)
    icon: str = ""

    # 权限
    required_capability: str = "basic_edit"  # 所需能力级别
    danger_level: int = 0  # 危险等级 0-10

    # 执行配置
    timeout: int = 30  # 超时秒数
    retryable: bool = True
    cacheable: bool = False

    # 状态
    enabled: bool = True
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.category, str):
            self.category = ActionCategory(self.category)
        if isinstance(self.return_type, str):
            self.return_type = ReturnType(self.return_type)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "handler": self.handler,
            "params": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "options": p.options,
                }
                for p in self.params
            ],
            "return_type": self.return_type.value if isinstance(self.return_type, ReturnType) else self.return_type,
            "category": self.category.value if isinstance(self.category, ActionCategory) else self.category,
            "keywords": self.keywords,
            "icon": self.icon,
            "required_capability": self.required_capability,
            "danger_level": self.danger_level,
            "timeout": self.timeout,
            "retryable": self.retryable,
            "cacheable": self.cacheable,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Action":
        params = []
        for p in data.get("params", []):
            if isinstance(p, dict):
                params.append(ActionParameter(**p))
            else:
                params.append(p)

        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            handler=data["handler"],
            params=params,
            return_type=ReturnType(data.get("return_type", "void")),
            category=ActionCategory(data.get("category", "custom")),
            keywords=data.get("keywords", []),
            icon=data.get("icon", ""),
            required_capability=data.get("required_capability", "basic_edit"),
            danger_level=data.get("danger_level", 0),
            timeout=data.get("timeout", 30),
            retryable=data.get("retryable", True),
            cacheable=data.get("cacheable", False),
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
        )


class ActionRepository:
    """动作仓库管理器"""

    # 内置动作
    BUILTIN_ACTIONS = [
        # ===== 路由相关 =====
        Action(
            id="route.quick_start",
            name="快速开始路由",
            description="快速启动智能路由功能",
            handler="route_engine.quick_start",
            category=ActionCategory.ROUTE,
            keywords=["路由", "启动", "开始", "quick", "start"],
            icon="🚀",
            danger_level=1,
        ),
        Action(
            id="route.test_url",
            name="测试URL",
            description="测试URL的可访问性",
            handler="route_engine.test_url",
            params=[
                ActionParameter(name="url", type="string", description="要测试的URL")
            ],
            return_type=ReturnType.BOOLEAN,
            category=ActionCategory.ROUTE,
            keywords=["测试", "URL", "检查", "连通性"],
            icon="🔍",
        ),
        Action(
            id="route.get_status",
            name="获取路由状态",
            description="获取当前路由系统的状态",
            handler="route_engine.get_status",
            return_type=ReturnType.OBJECT,
            category=ActionCategory.ROUTE,
            keywords=["状态", "路由", "状态"],
            icon="📊",
        ),
        Action(
            id="route.add_rule",
            name="添加路由规则",
            description="添加新的路由规则",
            handler="route_engine.add_rule",
            params=[
                ActionParameter(name="pattern", type="string", description="URL匹配模式"),
                ActionParameter(name="target", type="string", description="目标URL"),
            ],
            return_type=ReturnType.BOOLEAN,
            category=ActionCategory.ROUTE,
            keywords=["添加", "路由", "规则"],
            icon="➕",
            danger_level=3,
        ),

        # ===== 网络相关 =====
        Action(
            id="network.check_status",
            name="检查网络状态",
            description="检查当前网络连接状态",
            handler="network_utils.check_status",
            return_type=ReturnType.OBJECT,
            category=ActionCategory.NETWORK,
            keywords=["网络", "状态", "检查", "连接"],
            icon="🌐",
        ),
        Action(
            id="network.speed_test",
            name="网络测速",
            description="执行网络速度测试",
            handler="network_utils.speed_test",
            return_type=ReturnType.OBJECT,
            category=ActionCategory.NETWORK,
            keywords=["测速", "网速", "速度"],
            icon="⚡",
        ),

        # ===== AI相关 =====
        Action(
            id="ai.summarize",
            name="AI总结",
            description="使用AI总结文本内容",
            handler="ai_assistant.summarize",
            params=[
                ActionParameter(name="text", type="string", description="要总结的文本")
            ],
            return_type=ReturnType.STRING,
            category=ActionCategory.AI,
            keywords=["总结", "摘要", "AI"],
            icon="📝",
        ),
        Action(
            id="ai.translate",
            name="AI翻译",
            description="使用AI翻译文本",
            handler="ai_assistant.translate",
            params=[
                ActionParameter(name="text", type="string", description="要翻译的文本"),
                ActionParameter(name="target_lang", type="string", description="目标语言", required=False, default="中文"),
            ],
            return_type=ReturnType.STRING,
            category=ActionCategory.AI,
            keywords=["翻译", "语言"],
            icon="🌍",
        ),
        Action(
            id="ai.explain",
            name="AI解释",
            description="解释代码或复杂内容",
            handler="ai_assistant.explain",
            params=[
                ActionParameter(name="content", type="string", description="要解释的内容")
            ],
            return_type=ReturnType.STRING,
            category=ActionCategory.AI,
            keywords=["解释", "代码", "说明"],
            icon="💡",
        ),

        # ===== 系统相关 =====
        Action(
            id="system.open_url",
            name="打开URL",
            description="在浏览器中打开指定URL",
            handler="system_utils.open_browser",
            params=[
                ActionParameter(name="url", type="string", description="URL地址")
            ],
            return_type=ReturnType.VOID,
            category=ActionCategory.SYSTEM,
            keywords=["打开", "浏览器", "URL"],
            icon="🔗",
            danger_level=2,
        ),
        Action(
            id="system.clean_cache",
            name="清理缓存",
            description="清理系统临时文件和缓存",
            handler="system_utils.clean_cache",
            return_type=ReturnType.VOID,
            category=ActionCategory.SYSTEM,
            keywords=["清理", "缓存", "清理缓存"],
            icon="🧹",
            danger_level=5,
        ),
        Action(
            id="system.show_notification",
            name="显示通知",
            description="在系统中显示通知",
            handler="system_utils.show_notification",
            params=[
                ActionParameter(name="title", type="string", description="通知标题"),
                ActionParameter(name="message", type="string", description="通知内容"),
            ],
            return_type=ReturnType.VOID,
            category=ActionCategory.SYSTEM,
            keywords=["通知", "提示", "消息"],
            icon="🔔",
        ),
        Action(
            id="system.get_info",
            name="获取系统信息",
            description="获取系统基本信息",
            handler="system_utils.get_info",
            return_type=ReturnType.OBJECT,
            category=ActionCategory.SYSTEM,
            keywords=["系统", "信息"],
            icon="💻",
        ),

        # ===== 数据相关 =====
        Action(
            id="data.save",
            name="保存数据",
            description="保存数据到本地存储",
            handler="data_manager.save",
            params=[
                ActionParameter(name="key", type="string", description="数据键名"),
                ActionParameter(name="value", type="object", description="数据值"),
            ],
            return_type=ReturnType.BOOLEAN,
            category=ActionCategory.DATA,
            keywords=["保存", "存储"],
            icon="💾",
        ),
        Action(
            id="data.load",
            name="加载数据",
            description="从本地存储加载数据",
            handler="data_manager.load",
            params=[
                ActionParameter(name="key", type="string", description="数据键名"),
            ],
            return_type=ReturnType.OBJECT,
            category=ActionCategory.DATA,
            keywords=["加载", "读取"],
            icon="📂",
        ),

        # ===== UI相关 =====
        Action(
            id="ui.show_panel",
            name="显示面板",
            description="显示指定的面板",
            handler="ui_manager.show_panel",
            params=[
                ActionParameter(name="panel_id", type="string", description="面板ID")
            ],
            return_type=ReturnType.VOID,
            category=ActionCategory.UI,
            keywords=["显示", "面板", "打开"],
            icon="📋",
        ),
        Action(
            id="ui.hide_panel",
            name="隐藏面板",
            description="隐藏指定的面板",
            handler="ui_manager.hide_panel",
            params=[
                ActionParameter(name="panel_id", type="string", description="面板ID")
            ],
            return_type=ReturnType.VOID,
            category=ActionCategory.UI,
            keywords=["隐藏", "面板", "关闭"],
            icon="📋",
        ),
        Action(
            id="ui.refresh",
            name="刷新界面",
            description="刷新当前界面",
            handler="ui_manager.refresh",
            return_type=ReturnType.VOID,
            category=ActionCategory.UI,
            keywords=["刷新", "更新"],
            icon="🔄",
        ),
    ]

    def __init__(self):
        self.actions: dict[str, Action] = {}
        self.categories: dict[ActionCategory, list[str]] = defaultdict(list)
        self._keyword_index: dict[str, list[str]] = defaultdict(list)  # 关键词 -> action_id

        # 加载内置动作
        self._load_builtin_actions()

        # 动作处理器注册表
        self._handlers: dict[str, Callable] = {}

        # 注册默认处理器
        self._register_default_handlers()

    def _load_builtin_actions(self):
        """加载内置动作"""
        for action in self.BUILTIN_ACTIONS:
            self.actions[action.id] = action
            self.categories[action.category].append(action.id)
            self._index_keywords(action)

    def _index_keywords(self, action: Action):
        """索引动作关键词"""
        for keyword in action.keywords:
            keyword_lower = keyword.lower()
            if keyword_lower not in self._keyword_index:
                self._keyword_index[keyword_lower] = []
            self._keyword_index[keyword_lower].append(action.id)

    def register_action(self, action: Action):
        """注册新动作"""
        self.actions[action.id] = action
        self.categories[action.category].append(action.id)
        self._index_keywords(action)

    def unregister_action(self, action_id: str) -> bool:
        """注销动作"""
        if action_id in self.actions:
            action = self.actions.pop(action_id)
            if action.id in self.categories[action.category]:
                self.categories[action.category].remove(action.id)

            # 移除关键词索引
            for keyword in action.keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in self._keyword_index:
                    if action_id in self._keyword_index[keyword_lower]:
                        self._keyword_index[keyword_lower].remove(action_id)

            return True
        return False

    def get_action(self, action_id: str) -> Optional[Action]:
        """获取动作"""
        return self.actions.get(action_id)

    def get_actions_by_category(self, category: ActionCategory) -> list[Action]:
        """获取指定分类的所有动作"""
        action_ids = self.categories.get(category, [])
        return [self.actions[aid] for aid in action_ids if aid in self.actions]

    def search_actions(self, query: str, limit: int = 10) -> list[Action]:
        """
        搜索动作（基于关键词）

        Args:
            query: 搜索查询
            limit: 返回数量限制

        Returns:
            匹配的动作列表
        """
        query = query.lower().strip()
        if not query:
            return []

        matched_ids = set()

        # 完全匹配动作ID
        if query in self.actions:
            matched_ids.add(query)

        # 关键词匹配
        for keyword, action_ids in self._keyword_index.items():
            if query in keyword:
                matched_ids.update(action_ids)

        # 名称和描述匹配
        for action_id, action in self.actions.items():
            if query in action.name.lower() or query in action.description.lower():
                matched_ids.add(action_id)

        # 构建结果
        results = []
        for action_id in matched_ids:
            action = self.actions[action_id]
            # 计算匹配分数
            score = self._calculate_match_score(query, action)
            results.append((score, action))

        # 按分数排序
        results.sort(key=lambda x: x[0], reverse=True)
        return [action for _, action in results[:limit]]

    def _calculate_match_score(self, query: str, action: Action) -> float:
        """计算匹配分数"""
        score = 0.0

        # 名称完全匹配
        if query == action.name.lower():
            score += 1.0

        # 名称包含
        if query in action.name.lower():
            score += 0.5

        # 描述包含
        if query in action.description.lower():
            score += 0.3

        # 关键词匹配
        for keyword in action.keywords:
            if query in keyword.lower():
                score += 0.4

        # ID包含
        if query in action.id.lower():
            score += 0.2

        return score

    def find_action_by_description(self, description: str) -> Optional[Action]:
        """
        通过自然语言描述查找最佳匹配动作

        Args:
            description: 自然语言描述

        Returns:
            最佳匹配的动作，或None
        """
        results = self.search_actions(description, limit=1)
        return results[0] if results else None

    def register_handler(self, action_id: str, handler: Callable):
        """注册动作处理器"""
        self._handlers[action_id] = handler

    async def execute_action(
        self,
        action_id: str,
        params: dict = None,
        context: dict = None
    ) -> Any:
        """
        执行动作

        Args:
            action_id: 动作ID
            params: 动作参数
            context: 执行上下文

        Returns:
            动作执行结果
        """
        action = self.get_action(action_id)
        if not action:
            raise ValueError(f"Action not found: {action_id}")

        if not action.enabled:
            raise RuntimeError(f"Action is disabled: {action_id}")

        params = params or {}
        context = context or {}

        # 获取处理器
        handler = self._handlers.get(action_id)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    return await handler(**params)
                else:
                    return handler(**params)
            except Exception as e:
                raise RuntimeError(f"Action execution failed: {e}")
        else:
            # 没有注册处理器，返回模拟结果
            return {"status": "ok", "action_id": action_id, "params": params}

    def _register_default_handlers(self):
        """注册默认处理器"""
        # 这里可以注册一些模拟处理器用于测试
        pass

    def export_actions(self) -> str:
        """导出所有动作为JSON"""
        return json.dumps(
            [action.to_dict() for action in self.actions.values()],
            ensure_ascii=False,
            indent=2
        )

    def import_actions(self, json_str: str) -> int:
        """从JSON导入动作，返回导入数量"""
        try:
            data = json.loads(json_str)
            count = 0
            for action_data in data:
                action = Action.from_dict(action_data)
                self.register_action(action)
                count += 1
            return count
        except Exception:
            return 0


# 全局单例
_action_repository: Optional[ActionRepository] = None


def get_action_repository() -> ActionRepository:
    """获取动作仓库单例"""
    global _action_repository
    if _action_repository is None:
        _action_repository = ActionRepository()
    return _action_repository