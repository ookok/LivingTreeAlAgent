"""
智能客户端AI助手系统

核心功能：
1. 应用知识图谱 - UI结构映射、功能关系图、操作路径库
2. 深度链接与路由系统 - 统一URI协议、路由注册表
3. AI意图识别与动作映射 - 双层意图识别、上下文管理
4. 动态指引系统 - 多级指引、视觉表现层
5. 文档与配置集成 - 帮助文档映射、配置智能助手
"""

import re
import time
import uuid
import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple, Set, Callable
from enum import Enum, auto
from collections import defaultdict


# ==================== 数据模型 ====================

class IntentType(Enum):
    """一级意图分类"""
    FEATURE_QUERY = auto()      # 功能查询
    OPERATION_GUIDE = auto()    # 操作指导
    CONFIG_HELP = auto()        # 配置帮助
    TROUBLESHOOT = auto()       # 故障排查
    GENERAL_HELP = auto()       # 一般帮助
    NAVIGATION = auto()         # 导航跳转
    SETTINGS = auto()           # 设置操作
    UNKNOWN = auto()            # 未知意图


class SecondaryIntent(Enum):
    """二级意图分类"""
    # 功能查询
    WHAT_IS = auto()           # 是什么
    HOW_WORKS = auto()         # 如何工作
    FEATURE_LIST = auto()      # 功能列表
    WHERE_IS = auto()          # 在哪里
    
    # 操作指导
    HOW_TO_DO = auto()         # 如何做
    STEP_BY_STEP = auto()      # 分步指导
    QUICK_ACTION = auto()      # 快捷操作
    
    # 配置帮助
    HOW_TO_CONFIG = auto()     # 如何配置
    CONFIG_EXPLAIN = auto()    # 配置解释
    CONFIG_IMPORT_EXPORT = auto()  # 配置导入导出
    
    # 故障排查
    ERROR_FIX = auto()         # 错误修复
    ISSUE_DIAGNOSE = auto()     # 问题诊断
    RECOVERY = auto()          # 恢复操作
    
    # 设置操作
    OPEN_SETTINGS = auto()       # 打开设置
    UPDATE_CONFIG = auto()      # 更新配置
    RESET_CONFIG = auto()       # 重置配置


class GuideLevel(Enum):
    """指引级别"""
    SIMPLE = auto()            # 简单高亮
    STEP = auto()              # 分步指引
    INTERACTIVE = auto()       # 交互式引导


class ComponentType(Enum):
    """UI组件类型"""
    BUTTON = auto()
    INPUT = auto()
    DROPDOWN = auto()
    CHECKBOX = auto()
    RADIO = auto()
    SLIDER = auto()
    TOGGLE = auto()
    TABS = auto()
    TABLE = auto()
    LIST = auto()
    TREE = auto()
    DIALOG = auto()
    PANEL = auto()
    MENU = auto()
    TOOLBAR = auto()
    SIDEBAR = auto()
    CARD = auto()
    MODAL = auto()
    TOAST = auto()
    OTHER = auto()


class LinkType(Enum):
    """链接类型"""
    SIMPLE = auto()           # 简单跳转
    ACTION = auto()           # 操作链接
    GUIDE = auto()            # 指引链接
    CONFIG = auto()           # 配置链接


@dataclass
class UIComponent:
    """UI组件"""
    id: str
    type: ComponentType
    label: str
    description: str = ""
    tooltip: str = ""
    shortcut: str = ""  # 快捷键
    parent_id: str = ""
    children: List[str] = field(default_factory=list)
    related_docs: List[str] = field(default_factory=list)
    related_configs: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UIPage:
    """UI页面/窗口"""
    id: str
    title: str
    path: str
    description: str = ""
    components: Dict[str, UIComponent] = field(default_factory=dict)
    parent_page: str = ""
    child_pages: List[str] = field(default_factory=list)
    related_docs: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    route_pattern: str = ""
    
    def add_component(self, component: UIComponent):
        self.components[component.id] = component


@dataclass
class OperationStep:
    """操作步骤"""
    step_id: str
    page_id: str
    component_id: str
    action: str  # click, input, select, toggle, etc.
    value: Any = None
    description: str = ""
    expected_result: str = ""
    warning: str = ""
    timeout: float = 5.0


@dataclass
class OperationPath:
    """操作路径"""
    path_id: str
    name: str
    description: str
    from_page: str
    to_page: str
    steps: List[OperationStep]
    prerequisites: List[str] = field(default_factory=list)
    estimated_time: float = 0  # 秒
    difficulty: str = "easy"  # easy, medium, hard
    related_queries: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class Route:
    """路由定义"""
    route_id: str
    pattern: str  # URI pattern: app://settings/model?highlight=api_key
    page_id: str
    params: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable] = None
    preconditions: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)


@dataclass
class GuideStep:
    """指引步骤"""
    step_number: int
    page_id: str
    component_id: str
    instruction: str
    highlight: bool = True
    animation: str = ""  # pulse, arrow, circle, etc.
    expected_action: str = ""
    expected_result: str = ""
    skip_conditions: List[str] = field(default_factory=list)
    tips: str = ""
    warning: str = ""


@dataclass
class Guide:
    """指引定义"""
    guide_id: str
    name: str
    description: str
    level: GuideLevel
    target_page: str
    target_component: str = ""
    steps: List[GuideStep] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    completion_actions: List[str] = field(default_factory=list)
    abort_actions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class UserContext:
    """用户上下文"""
    user_id: str = ""
    current_page: str = ""
    current_components: List[str] = field(default_factory=list)
    session_history: List[str] = field(default_factory=list)  # 页面访问历史
    operation_history: List[str] = field(default_factory=list)  # 操作历史
    preferences: Dict[str, Any] = field(default_factory=dict)
    learned_patterns: List[str] = field(default_factory=list)  # 学习到的用户习惯
    skill_level: str = "beginner"  # beginner, intermediate, expert


@dataclass
class ConversationContext:
    """会话上下文"""
    conversation_id: str = ""
    messages: List[Dict[str, str]] = field(default_factory=list)  # role, content
    current_intent: IntentType = IntentType.UNKNOWN
    pending_operations: List[str] = field(default_factory=list)
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    related_guides: List[str] = field(default_factory=list)
    related_routes: List[str] = field(default_factory=list)


@dataclass
class IntentResult:
    """意图识别结果"""
    primary_intent: IntentType
    secondary_intent: SecondaryIntent
    confidence: float
    entities: Dict[str, Any]
    related_pages: List[str]
    related_guides: List[str]
    suggested_actions: List[str]
    response_template: str = ""
    raw_query: str = ""


@dataclass
class NavigationResult:
    """导航结果"""
    success: bool
    target_page: str = ""
    target_component: str = ""
    guide_id: str = ""
    route_url: str = ""
    message: str = ""
    actions: List[Dict[str, Any]] = field(default_factory=list)
    docs_links: List[str] = field(default_factory=list)
