"""
NL UI Manager - 自然语言UI生成管理器
=======================================

协调所有NL UI Generator模块的统一入口。

工作流程:
    用户输入自然语言
         ↓
    IntentParser 解析意图
         ↓
    查找/生成对应动作
         ↓
    SecurityAuditor 审计代码
         ↓
    ScriptSandbox 安全执行
         ↓
    UITemplateEngine 生成UI
         ↓
    UIRealtimePreview 预览确认
         ↓
    HotReloadManager 热更新
"""

import asyncio
from typing import Optional, Any, Callable
from dataclasses import dataclass, field

from .intent_parser import IntentParser, Intent, IntentType, get_intent_parser
from .ui_template_engine import UITemplateEngine, UITemplate, TemplateComponent, get_template_engine
from .action_repository import ActionRepository, Action, get_action_repository
from .ai_code_generator import AICodeGenerator, GeneratedCode, get_code_generator
from .script_sandbox import ScriptSandbox, SandboxResult, SecurityLevel, get_sandbox
from .ui_realtime_preview import UIRealtimePreview, PreviewResult, PreviewChange, get_preview
from .change_history import ChangeHistory, ChangeRecord, ChangeType, get_change_history
from .security_auditor import SecurityAuditor, AuditResult, get_security_auditor
from .hot_reload_manager import HotReloadManager, ReloadEvent, ReloadEventType, get_hot_reload_manager
from .component_registry import ComponentRegistry, ComponentDefinition, get_component_registry


@dataclass
class NLUIRequest:
    """自然语言UI请求"""
    text: str  # 用户输入的自然语言
    context: dict = field(default_factory=dict)  # 上下文
    user_id: str = "system"
    preview_only: bool = False  # 仅预览不保存


@dataclass
class NLUIResponse:
    """自然语言UI响应"""
    success: bool
    message: str = ""
    intent: Intent = None
    action: Action = None
    generated_code: GeneratedCode = None
    code_audit: AuditResult = None
    preview_result: PreviewResult = None
    changes: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class NLUIDriver:
    """自然语言UI驱动"""

    def __init__(self):
        # 初始化所有模块
        self.intent_parser = get_intent_parser()
        self.template_engine = get_template_engine()
        self.action_repository = get_action_repository()
        self.code_generator = get_code_generator()
        self.sandbox = get_sandbox()
        self.preview = get_preview()
        self.change_history = get_change_history()
        self.security_auditor = get_security_auditor()
        self.hot_reload = get_hot_reload_manager()
        self.component_registry = get_component_registry()

        # 用户会话
        self.sessions: dict = {}

    async def process(self, request: NLUIRequest) -> NLUIResponse:
        """
        处理自然语言UI请求

        Args:
            request: 请求对象

        Returns:
            NLUIResponse: 响应对象
        """
        response = NLUIResponse(success=False)

        try:
            # 1. 解析意图
            response.intent = self.intent_parser.parse(request.text)
            if response.intent.type == IntentType.UNKNOWN:
                response.message = f"无法理解: {request.text}"
                return response

            # 2. 根据意图类型处理
            if response.intent.type == IntentType.ADD_ELEMENT:
                response = await self._handle_add_element(request, response)
            elif response.intent.type == IntentType.BIND_ACTION:
                response = await self._handle_bind_action(request, response)
            elif response.intent.type == IntentType.UNDO:
                response = await self._handle_undo(request, response)
            elif response.intent.type == IntentType.REDO:
                response = await self._handle_redo(request, response)
            else:
                response.message = f"暂不支持的意图类型: {response.intent.type.value}"
                return response

            response.success = True
            response.message = "处理成功"

        except Exception as e:
            response.success = False
            response.message = f"处理失败: {str(e)}"

        return response

    async def _handle_add_element(
        self,
        request: NLUIRequest,
        response: NLUIResponse,
    ) -> NLUIResponse:
        """处理添加元素"""
        params = response.intent.params

        # 获取目标面板和元素描述
        target_panel = params.get("target", "default")
        element_desc = params.get("element", "")

        # 查找匹配的动作
        action = self.action_repository.find_action_by_description(element_desc)

        if not action:
            # 生成新动作代码
            response.generated_code = await self.code_generator.generate_async(
                description=f"创建{element_desc}功能",
                intent_type="button_handler",
            )

            # 审计生成的代码
            response.code_audit = self.security_auditor.audit(response.generated_code.code)

            if not response.code_audit.safe:
                response.message = f"生成的代码存在安全风险: {response.code_audit.suggestions}"
                return response

        response.action = action
        response.message = f"准备添加 {element_desc} 到 {target_panel}"
        return response

    async def _handle_bind_action(
        self,
        request: NLUIRequest,
        response: NLUIResponse,
    ) -> NLUIResponse:
        """处理绑定动作"""
        params = response.intent.params

        element_desc = params.get("element", "")
        action_desc = params.get("action", "")

        # 查找动作
        action = self.action_repository.find_action_by_description(action_desc)

        if not action:
            # 生成动作代码
            response.generated_code = await self.code_generator.generate_async(
                description=action_desc,
                intent_type="simple_action",
            )

            # 审计
            response.code_audit = self.security_auditor.audit(response.generated_code.code)

            if not response.code_audit.safe:
                response.message = f"动作代码存在安全风险"
                return response

        response.action = action
        response.message = f"准备绑定 {action_desc} 到 {element_desc}"
        return response

    async def _handle_undo(
        self,
        request: NLUIRequest,
        response: NLUIResponse,
    ) -> NLUIResponse:
        """处理撤销"""
        if self.change_history.can_undo():
            record = self.change_history.undo()
            response.message = f"已撤销: {record.description}"
        else:
            response.message = "没有可撤销的操作"
        return response

    async def _handle_redo(
        self,
        request: NLUIRequest,
        response: NLUIResponse,
    ) -> NLUIResponse:
        """处理重做"""
        if self.change_history.can_redo():
            record = self.change_history.redo()
            response.message = f"已重做: {record.description}"
        else:
            response.message = "没有可重做的操作"
        return response

    def get_capability_level(self, user_id: str = "system") -> str:
        """获取用户能力级别"""
        # 简单实现，可扩展
        return "advanced_edit"

    def get_available_templates(self) -> list[dict]:
        """获取可用模板列表"""
        templates = self.template_engine.get_all_templates()
        return [t.to_dict() for t in templates]

    def get_available_actions(self) -> list[dict]:
        """获取可用动作列表"""
        actions = self.action_repository.get_all_actions()
        return [a.to_dict() for a in actions]

    def get_component_library(self) -> list[dict]:
        """获取组件库"""
        components = self.component_registry.get_all()
        return [c.to_dict() for c in components]


# 全局单例
_nl_ui_driver: Optional[NLUIDriver] = None


def get_nl_ui_driver() -> NLUIDriver:
    """获取NL UI驱动单例"""
    global _nl_ui_driver
    if _nl_ui_driver is None:
        _nl_ui_driver = NLUIDriver()
    return _nl_ui_driver