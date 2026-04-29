"""
变量解析器
Variable Resolver - 变量类型系统、上下文感知
"""

import re
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
import threading

from .models import (
    VariableDefinition, VariableType, VariableSource,
    SystemVariables, MessagePattern
)


@dataclass
class VariableValue:
    """变量值"""
    name: str
    value: Any
    source: str = ""
    confidence: float = 1.0
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class ResolverContext:
    """解析上下文"""
    user_input: str = ""                       # 用户输入
    conversation_history: List[Dict] = field(default_factory=list)  # 对话历史
    user_profile: Dict[str, Any] = field(default_factory=dict)      # 用户画像
    system_state: Dict[str, Any] = field(default_factory=dict)     # 系统状态
    environment: Dict[str, Any] = field(default_factory=dict)      # 环境信息
    current_time: str = ""                     # 当前时间
    session_id: str = ""                       # 会话ID
    user_id: str = ""                          # 用户ID
    custom_data: Dict[str, Any] = field(default_factory=dict)      # 自定义数据

    def __post_init__(self):
        if not self.current_time:
            self.current_time = datetime.now().isoformat()


class VariableResolver:
    """变量解析器"""

    # 变量替换正则表达式
    VARIABLE_PATTERN = re.compile(r'\{(\w+)\}')
    COMPLEX_VAR_PATTERN = re.compile(r'\{(\w+)(?::([^}]+))?\}')

    def __init__(self):
        self._custom_resolvers: Dict[str, Callable] = {}
        self._cache: Dict[str, VariableValue] = {}
        self._cache_lock = threading.Lock()
        self._default_context = ResolverContext()
        self._init_builtin_resolvers()

    def _init_builtin_resolvers(self):
        """初始化内置解析器"""
        # 系统变量解析器
        self._custom_resolvers["current_time"] = self._resolve_current_time
        self._custom_resolvers["current_date"] = self._resolve_current_date
        self._custom_resolvers["timestamp"] = self._resolve_timestamp

        # 用户变量解析器
        self._custom_resolvers["username"] = self._resolve_username
        self._custom_resolvers["user_id"] = self._resolve_user_id
        self._custom_resolvers["user_role"] = self._resolve_user_role

        # 会话变量解析器
        self._custom_resolvers["session_id"] = self._resolve_session_id
        self._custom_resolvers["conversation_topic"] = self._resolve_conversation_topic
        self._custom_resolvers["message_count"] = self._resolve_message_count

        # 内容变量解析器
        self._custom_resolvers["user_input"] = self._resolve_user_input
        self._custom_resolvers["previous_message"] = self._resolve_previous_message
        self._custom_resolvers["conversation_context"] = self._resolve_conversation_context

        # 智能变量解析器
        self._custom_resolvers["user_intent"] = self._resolve_user_intent
        self._custom_resolvers["user_sentiment"] = self._resolve_user_sentiment
        self._custom_resolvers["domain_knowledge"] = self._resolve_domain_knowledge
        self._custom_resolvers["writing_style"] = self._resolve_writing_style

    def _get_cache_key(self, var_name: str, context: ResolverContext) -> str:
        """获取缓存键"""
        return f"{var_name}:{context.session_id}:{len(context.conversation_history)}"

    def register_resolver(self, var_name: str, resolver: Callable):
        """注册自定义解析器"""
        self._custom_resolvers[var_name] = resolver

    def set_default_context(self, context: ResolverContext):
        """设置默认上下文"""
        self._default_context = context

    def resolve(
        self,
        template: str,
        variables: Dict[str, VariableDefinition],
        context: ResolverContext = None
    ) -> str:
        """解析模板中的变量"""
        if context is None:
            context = self._default_context

        result = template

        # 查找所有变量占位符
        matches = list(self.COMPLEX_VAR_PATTERN.finditer(template))

        # 从后向前替换（避免位置变化）
        for match in reversed(matches):
            var_name = match.group(1)
            modifier = match.group(2)  # 可选的修饰符

            if var_name in variables:
                var_def = variables[var_name]
                value = self.resolve_variable(var_name, var_def, context)
                value = self._apply_modifier(value, modifier)
            else:
                # 尝试自动解析
                value = self.auto_resolve(var_name, context)

            result = result[:match.start()] + str(value) + result[match.end():]

        return result

    def resolve_variable(
        self,
        var_name: str,
        var_def: VariableDefinition,
        context: ResolverContext = None
    ) -> Any:
        """解析单个变量"""
        if context is None:
            context = self._default_context

        # 检查缓存
        cache_key = self._get_cache_key(var_name, context)
        with self._cache_lock:
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                # 缓存5分钟内有效
                if (datetime.now() - datetime.fromisoformat(cached.timestamp)).seconds < 300:
                    return cached.value

        # 优先使用自定义解析器
        if var_name in self._custom_resolvers:
            resolver = self._custom_resolvers[var_name]
            value = resolver(context)
        else:
            # 根据变量类型解析
            value = self._resolve_by_type(var_def, context)

        # 缓存结果
        with self._cache_lock:
            self._cache[cache_key] = VariableValue(
                name=var_name,
                value=value,
                source=var_def.source.value if hasattr(var_def.source, 'value') else str(var_def.source)
            )

        return value

    def auto_resolve(self, var_name: str, context: ResolverContext = None) -> Any:
        """自动解析变量"""
        if context is None:
            context = self._default_context

        # 检查是否有自定义解析器
        if var_name in self._custom_resolvers:
            return self._custom_resolvers[var_name](context)

        # 尝试从上下文中获取
        if var_name in context.custom_data:
            return context.custom_data[var_name]
        if var_name in context.user_profile:
            return context.user_profile[var_name]
        if var_name in context.system_state:
            return context.system_state[var_name]

        # 检查环境变量
        if var_name in context.environment:
            return context.environment[var_name]

        return f"{{{var_name}}}"  # 返回原占位符

    def _resolve_by_type(
        self,
        var_def: VariableDefinition,
        context: ResolverContext
    ) -> Any:
        """根据变量类型解析"""
        var_type = var_def.var_type
        if hasattr(var_type, 'value'):
            var_type = var_type.value

        source = var_def.source
        if hasattr(source, 'value'):
            source = source.value

        # 根据来源获取值
        if source == "conversation_history":
            return self._get_from_history(var_def.name, context)
        elif source == "current_message":
            return context.user_input
        elif source == "user_profile":
            return context.user_profile.get(var_def.name, var_def.default)
        elif source == "system_state":
            return context.system_state.get(var_def.name, var_def.default)
        elif source == "environment":
            return context.environment.get(var_def.name, var_def.default)
        else:
            return var_def.default

    def _get_from_history(self, var_name: str, context: ResolverContext) -> Any:
        """从历史中获取"""
        if not context.conversation_history:
            return None

        # 根据变量名尝试匹配
        if var_name == "previous_message":
            for msg in reversed(context.conversation_history):
                if msg.get("role") == "user":
                    return msg.get("content", "")
        elif var_name == "conversation_context":
            return "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                for msg in context.conversation_history[-5:]
            ])

        return None

    def _apply_modifier(self, value: Any, modifier: str) -> Any:
        """应用修饰符"""
        if not modifier or value is None:
            return value

        modifiers = modifier.split("|")
        for mod in modifiers:
            mod = mod.strip()
            if mod == "upper":
                value = str(value).upper()
            elif mod == "lower":
                value = str(value).lower()
            elif mod == "title":
                value = str(value).title()
            elif mod == "capitalize":
                value = str(value).capitalize()
            elif mod == "strip":
                value = str(value).strip()
            elif mod == "length":
                value = len(str(value))
            elif mod == "first":
                value = str(value).split()[0] if str(value) else ""
            elif mod == "last":
                value = str(value).split()[-1] if str(value) else ""
            elif mod == "truncate":
                # 格式: truncate:50
                parts = mod.split(":")
                if len(parts) > 1:
                    max_len = int(parts[1])
                    value = str(value)[:max_len] + "..." if len(str(value)) > max_len else str(value)
            elif mod == "json":
                try:
                    value = json.dumps(value, ensure_ascii=False)
                except:
                    pass
            elif mod == "default" and not value:
                value = modifier.split(":")[1] if ":" in modifier else value

        return value

    # ============ 内置解析器实现 ============

    def _resolve_current_time(self, context: ResolverContext) -> str:
        """解析当前时间"""
        return datetime.now().strftime("%H:%M:%S")

    def _resolve_current_date(self, context: ResolverContext) -> str:
        """解析当前日期"""
        return datetime.now().strftime("%Y年%m月%d日")

    def _resolve_timestamp(self, context: ResolverContext) -> str:
        """解析时间戳"""
        return str(int(datetime.now().timestamp()))

    def _resolve_username(self, context: ResolverContext) -> str:
        """解析用户名"""
        return context.user_profile.get("name", context.user_profile.get("username", "用户"))

    def _resolve_user_id(self, context: ResolverContext) -> str:
        """解析用户ID"""
        return context.user_id or "anonymous"

    def _resolve_user_role(self, context: ResolverContext) -> str:
        """解析用户角色"""
        return context.user_profile.get("role", "普通用户")

    def _resolve_session_id(self, context: ResolverContext) -> str:
        """解析会话ID"""
        return context.session_id or "no_session"

    def _resolve_conversation_topic(self, context: ResolverContext) -> str:
        """解析对话主题"""
        if context.conversation_history:
            # 简单的主题提取：取第一条消息的内容作为主题
            first_msg = context.conversation_history[0]
            content = first_msg.get("content", "")
            return content[:50] + "..." if len(content) > 50 else content
        return "一般对话"

    def _resolve_message_count(self, context: ResolverContext) -> str:
        """解析消息数量"""
        return str(len(context.conversation_history))

    def _resolve_user_input(self, context: ResolverContext) -> str:
        """解析用户输入"""
        return context.user_input

    def _resolve_previous_message(self, context: ResolverContext) -> str:
        """解析上一条消息"""
        for msg in reversed(context.conversation_history):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    def _resolve_conversation_context(self, context: ResolverContext) -> str:
        """解析对话上下文"""
        if not context.conversation_history:
            return ""
        recent = context.conversation_history[-5:] if len(context.conversation_history) > 5 else context.conversation_history
        return "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in recent
        ])

    def _resolve_user_intent(self, context: ResolverContext) -> str:
        """解析用户意图（简化实现）"""
        if not context.user_input:
            return "未知"
        # 简单的关键词匹配
        input_lower = context.user_input.lower()
        if any(k in input_lower for k in ["分析", "分析一下", "请分析"]):
            return "分析请求"
        elif any(k in input_lower for k in ["写", "帮我写", "创作"]):
            return "写作请求"
        elif any(k in input_lower for k in ["代码", "程序", "函数"]):
            return "编程请求"
        elif any(k in input_lower for k in ["比较", "选择", "决策"]):
            return "决策请求"
        return "一般请求"

    def _resolve_user_sentiment(self, context: ResolverContext) -> str:
        """解析用户情感（简化实现）"""
        if not context.user_input:
            return "中性"
        # 简单情感分析
        positive_words = ["好", "棒", "优秀", "喜欢", "谢谢", "很好", "不错", "期待"]
        negative_words = ["问题", "错误", "失败", "糟糕", "不喜欢", "麻烦", "困扰"]

        input_str = context.user_input
        pos_count = sum(1 for w in positive_words if w in input_str)
        neg_count = sum(1 for w in negative_words if w in input_str)

        if pos_count > neg_count:
            return "正面"
        elif neg_count > pos_count:
            return "负面"
        return "中性"

    def _resolve_domain_knowledge(self, context: ResolverContext) -> str:
        """解析领域知识"""
        return context.user_profile.get("domain", "通用")

    def _resolve_writing_style(self, context: ResolverContext) -> str:
        """解析写作风格"""
        return context.user_profile.get("writing_style", "专业严谨")

    # ============ 批量解析 ============

    def resolve_all(
        self,
        variables: Dict[str, VariableDefinition],
        context: ResolverContext = None
    ) -> Dict[str, Any]:
        """批量解析所有变量"""
        if context is None:
            context = self._default_context

        results = {}
        for var_name, var_def in variables.items():
            results[var_name] = self.resolve_variable(var_name, var_def, context)

        return results

    def get_undefined_variables(self, template: str) -> List[str]:
        """获取模板中未定义的变量"""
        matches = self.VARIABLE_PATTERN.findall(template)
        return list(set(matches))

    def validate_variables(
        self,
        variables: Dict[str, VariableDefinition],
        context: ResolverContext = None
    ) -> Dict[str, List[str]]:
        """验证变量，返回验证结果"""
        if context is None:
            context = self._default_context

        errors = {}
        warnings = {}

        for var_name, var_def in variables.items():
            var_errors = []
            var_warnings = []

            # 检查必需变量
            if var_def.required:
                value = self.resolve_variable(var_name, var_def, context)
                if not value or value == f"{{{var_name}}}":
                    var_errors.append(f"必需变量 '{var_name}' 未提供值")

            # 检查默认值
            if not var_def.default and not var_def.required:
                var_warnings.append(f"变量 '{var_name}' 没有默认值")

            if var_errors:
                errors[var_name] = var_errors
            if var_warnings:
                warnings[var_name] = var_warnings

        return {"errors": errors, "warnings": warnings}

    def clear_cache(self):
        """清除缓存"""
        with self._cache_lock:
            self._cache.clear()


# 全局实例
_resolver_instance = None


def get_variable_resolver() -> VariableResolver:
    """获取变量解析器实例"""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = VariableResolver()
    return _resolver_instance


# ============ 上下文构建器 ============

class ContextBuilder:
    """上下文构建器"""

    @staticmethod
    def build_from_conversation(
        user_input: str,
        history: List[Dict],
        user_profile: Dict = None,
        session_id: str = ""
    ) -> ResolverContext:
        """从对话构建上下文"""
        return ResolverContext(
            user_input=user_input,
            conversation_history=history or [],
            user_profile=user_profile or {},
            session_id=session_id,
            current_time=datetime.now().isoformat()
        )

    @staticmethod
    def build_minimal(
        user_input: str,
        session_id: str = ""
    ) -> ResolverContext:
        """构建最小上下文"""
        return ResolverContext(
            user_input=user_input,
            session_id=session_id,
            current_time=datetime.now().isoformat()
        )

    @staticmethod
    def enrich_context(
        context: ResolverContext,
        **kwargs
    ) -> ResolverContext:
        """丰富上下文"""
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)
            else:
                context.custom_data[key] = value
        return context
