"""
智能客户端AI助手系统 - 核心模块

将AI助手从"问答机"升级为"软件导航员"，提供：
1. 应用知识图谱
2. 深度链接与路由系统
3. AI意图识别与动作映射
4. 动态指引系统
5. 文档与配置集成
"""

import time
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass

from .models import (
    IntentType, IntentResult, NavigationResult, 
    UserContext, ConversationContext
)
from .knowledge_graph import get_knowledge_graph, KnowledgeGraph
from .intent_recognizer import get_intent_recognizer, IntentRecognizer
from .guide_system import get_guide_system, GuideSystem, GuideState


@dataclass
class AssistantResponse:
    """助手响应"""
    text: str
    navigation: NavigationResult
    show_guide: bool = False
    guide_steps: List[str] = None
    suggestions: List[str] = None
    confidence: float = 0.0
    
    def __post_init__(self):
        if self.guide_steps is None:
            self.guide_steps = []
        if self.suggestions is None:
            self.suggestions = []


class SmartAssistant:
    """
    智能客户端AI助手
    
    将AI助手从"问答机"升级为"软件导航员"
    """
    
    def __init__(self):
        # 核心组件
        self.kg: KnowledgeGraph = get_knowledge_graph()
        self.recognizer: IntentRecognizer = get_intent_recognizer()
        self.guide_system: GuideSystem = get_guide_system()
        
        # 上下文管理
        self.user_context = UserContext()
        self.conversation_context = ConversationContext()
        
        # 回调函数
        self.navigation_callback: Optional[Callable] = None
        self.guide_callback: Optional[Callable] = None
        
        # 注册指引系统回调
        self.guide_system.register_callback("on_navigate", self._handle_navigate)
    
    # ==================== 主交互接口 ====================
    
    def chat(self, message: str) -> AssistantResponse:
        """
        处理用户消息
        
        Args:
            message: 用户消息
            
        Returns:
            AssistantResponse: 助手响应
        """
        # 1. 意图识别
        intent_result = self.recognizer.recognize(
            message, 
            user_ctx=self.user_context,
            conv_ctx=self.conversation_context
        )
        
        # 2. 生成响应
        response_text, navigation = self.recognizer.generate_response(
            intent_result,
            user_ctx=self.user_context
        )
        
        # 3. 更新上下文
        self._update_context(intent_result, message)
        
        # 4. 准备指引信息
        guide_steps = []
        show_guide = False
        
        if intent_result.related_guides:
            for guide_id in intent_result.related_guides:
                guides = self.kg.find_guide(tags=[guide_id])
                if guides:
                    guide_steps = [
                        self.guide_system.render_step_card(step) 
                        for step in guides[0].steps
                    ]
                    show_guide = True
                    break
        
        # 5. 生成建议
        suggestions = self._generate_suggestions(intent_result, navigation)
        
        return AssistantResponse(
            text=response_text,
            navigation=navigation,
            show_guide=show_guide,
            guide_steps=guide_steps,
            suggestions=suggestions,
            confidence=intent_result.confidence
        )
    
    def process_link(self, uri: str) -> bool:
        """
        处理深度链接
        
        Args:
            uri: 统一资源标识符
            
        Returns:
            是否处理成功
        """
        # 解析路由
        route_result = self.kg.resolve_route(uri)
        
        if route_result:
            route, params = route_result
            
            # 触发导航回调
            if self.navigation_callback:
                self.navigation_callback(
                    page_id=route.page_id,
                    params=params,
                    route_url=uri
                )
            
            # 更新用户上下文
            self.user_context.current_page = route.page_id
            self.user_context.session_history.append(route.page_id)
            
            return True
        
        return False
    
    # ==================== 指引控制 ====================
    
    def start_guide(self, guide_id: str) -> bool:
        """开始指引"""
        guides = self.kg.find_guide(tags=[guide_id])
        if not guides:
            return False
        
        return self.guide_system.start_guide(guides[0])
    
    def get_guide_progress(self) -> Dict[str, Any]:
        """获取指引进度"""
        return self.guide_system.get_progress()
    
    def guide_next_step(self, success: bool = True, error: str = "") -> Optional[str]:
        """指引下一步"""
        next_step = self.guide_system.next_step(success, error)
        if next_step:
            return self.guide_system.render_step_card(next_step)
        return None
    
    def guide_skip(self) -> Optional[str]:
        """跳过当前步骤"""
        next_step = self.guide_system.skip_step()
        if next_step:
            return self.guide_system.render_step_card(next_step)
        return None
    
    def guide_abort(self):
        """中止指引"""
        self.guide_system.abort_guide()
    
    def is_guide_running(self) -> bool:
        """检查指引是否运行中"""
        return self.guide_system.is_running()
    
    # ==================== 知识管理 ====================
    
    def register_page(self, page_id: str, title: str, path: str, 
                      description: str = "", tags: List[str] = None) -> bool:
        """注册页面"""
        from .models import UIPage
        page = UIPage(
            id=page_id,
            title=title,
            path=path,
            description=description,
            tags=tags or []
        )
        return self.kg.register_page(page)
    
    def register_component(self, page_id: str, component_id: str, 
                          label: str, component_type: str = "OTHER",
                          description: str = "") -> bool:
        """注册组件"""
        from .models import UIComponent, ComponentType
        
        # 解析组件类型
        comp_type = ComponentType.OTHER
        for ct in ComponentType:
            if ct.name.lower() == component_type.lower():
                comp_type = ct
                break
        
        component = UIComponent(
            id=component_id,
            type=comp_type,
            label=label,
            description=description
        )
        return self.kg.register_component(page_id, component)
    
    def register_route(self, page_id: str, pattern: str) -> bool:
        """注册路由"""
        from .models import Route
        
        route = Route(
            route_id=f"route_{page_id}",
            pattern=pattern,
            page_id=page_id
        )
        return self.kg.register_route(route)
    
    def register_operation_path(self, path_id: str, name: str, from_page: str,
                               to_page: str, steps: List[Dict]) -> bool:
        """注册操作路径"""
        from .models import OperationPath, OperationStep
        
        op_steps = []
        for i, step_data in enumerate(steps, 1):
            step = OperationStep(
                step_id=f"step_{i}",
                page_id=step_data.get("page_id", ""),
                component_id=step_data.get("component_id", ""),
                action=step_data.get("action", "click"),
                description=step_data.get("description", "")
            )
            op_steps.append(step)
        
        path = OperationPath(
            path_id=path_id,
            name=name,
            description=name,
            from_page=from_page,
            to_page=to_page,
            steps=op_steps,
            related_queries=[name]
        )
        return self.kg.register_operation_path(path)
    
    # ==================== 上下文管理 ====================
    
    def _update_context(self, intent_result: IntentResult, message: str):
        """更新对话上下文"""
        self.conversation_context.messages.append({
            "role": "user",
            "content": message,
            "intent": intent_result.primary_intent.name,
            "confidence": intent_result.confidence
        })
        self.conversation_context.current_intent = intent_result.primary_intent
        
        # 限制历史长度
        if len(self.conversation_context.messages) > 50:
            self.conversation_context.messages = self.conversation_context.messages[-50:]
        
        # 更新相关页面
        if intent_result.related_pages:
            self.conversation_context.related_routes = intent_result.related_pages
    
    def _generate_suggestions(self, intent_result: IntentResult,
                             navigation: NavigationResult) -> List[str]:
        """生成建议列表"""
        suggestions = []
        
        # 基于意图的建议
        if intent_result.primary_intent == IntentType.NAVIGATION:
            if navigation.target_page:
                suggestions.append(f"前往 {navigation.target_page}")
        
        elif intent_result.primary_intent == IntentType.OPERATION_GUIDE:
            suggestions.append("开始操作指引")
            suggestions.append("查看详细步骤")
        
        elif intent_result.primary_intent == IntentType.CONFIG_HELP:
            suggestions.append("开始配置向导")
            suggestions.append("查看配置文档")
        
        # 导航相关的建议
        if navigation.success and navigation.target_page:
            suggestions.append(f"打开 {navigation.target_page} 页面")
        
        # 指引相关的建议
        if intent_result.related_guides:
            suggestions.append("查看交互式指引")
        
        return suggestions[:4]
    
    def _handle_navigate(self, page_id: str, **kwargs):
        """处理导航回调"""
        if self.navigation_callback:
            self.navigation_callback(page_id=page_id, **kwargs)
    
    # ==================== 统计与诊断 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取系统统计"""
        return {
            "knowledge_base": self.kg.get_stats(),
            "guide_system": self.guide_system.get_execution_stats(),
            "conversation": {
                "message_count": len(self.conversation_context.messages),
                "current_intent": self.conversation_context.current_intent.name,
                "history_length": len(self.conversation_context.messages)
            },
            "user_context": {
                "current_page": self.user_context.current_page,
                "skill_level": self.user_context.skill_level
            }
        }
    
    def export_knowledge_base(self) -> Dict[str, Any]:
        """导出知识库"""
        return self.kg.export_knowledge_base()
    
    def diagnose(self) -> Dict[str, Any]:
        """诊断系统状态"""
        return {
            "status": "healthy",
            "knowledge_graph": {
                "pages": len(self.kg.pages),
                "routes": len(self.kg.routes),
                "paths": len(self.kg.operation_paths),
                "guides": len(self.kg.guides)
            },
            "guide_running": self.guide_system.is_running(),
            "context_active": len(self.conversation_context.messages) > 0
        }


# ==================== 便捷函数 ====================

_assistant_instance = None

def get_smart_assistant() -> SmartAssistant:
    """获取智能助手单例"""
    global _assistant_instance
    if _assistant_instance is None:
        _assistant_instance = SmartAssistant()
    return _assistant_instance


def process_query(query: str) -> AssistantResponse:
    """快捷函数：处理用户查询"""
    return get_smart_assistant().chat(query)


def navigate_to(uri: str) -> bool:
    """快捷函数：导航到指定URI"""
    return get_smart_assistant().process_link(uri)


def start_tutorial(guide_id: str) -> bool:
    """快捷函数：开始教程指引"""
    return get_smart_assistant().start_guide(guide_id)
