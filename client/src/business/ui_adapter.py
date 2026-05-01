"""
UI Adapter - 前端集成适配器

提供DynamicUIEngine与前端Vue组件的桥接能力：
1. Schema转换 - 将UI Schema转换为Vue组件配置
2. 事件桥接 - 处理前端事件并传递给后端
3. 实时同步 - 支持前后端状态同步
4. 组件注册 - 管理可渲染的组件列表
"""

import json
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型"""
    COMPONENT_CLICK = "component_click"
    FORM_SUBMIT = "form_submit"
    VALUE_CHANGE = "value_change"
    FEEDBACK = "feedback"
    NAVIGATION = "navigation"


@dataclass
class UIEvent:
    """UI事件"""
    event_id: str
    event_type: EventType
    component_id: str
    payload: Dict[str, Any]
    timestamp: float


@dataclass
class RenderResult:
    """渲染结果"""
    success: bool
    html: Optional[str] = None
    components: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class UIAdapter:
    """
    UI适配器
    
    核心功能：
    1. 将DynamicUIEngine的Schema转换为前端可渲染的格式
    2. 处理前端事件并传递给后端服务
    3. 管理组件注册和渲染映射
    """
    
    def __init__(self):
        # 组件渲染映射
        self._component_renderers: Dict[str, Callable] = self._init_renderers()
        
        # 事件处理器
        self._event_handlers: Dict[EventType, List[Callable]] = {}
        
        # 注册默认事件处理器
        self._register_default_handlers()
        
        # 当前渲染状态
        self._current_schema: Optional[Dict[str, Any]] = None
        
        # 表单数据缓存
        self._form_data: Dict[str, Any] = {}
        
        logger.info("✅ UIAdapter 初始化完成")
    
    def _init_renderers(self) -> Dict[str, Callable]:
        """初始化组件渲染器"""
        return {
            "text_input": self._render_text_input,
            "textarea": self._render_textarea,
            "select": self._render_select,
            "multi_select": self._render_multi_select,
            "checkbox": self._render_checkbox,
            "radio": self._render_radio,
            "slider": self._render_slider,
            "date_picker": self._render_date_picker,
            "file_upload": self._render_file_upload,
            "text": self._render_text,
            "heading": self._render_heading,
            "image": self._render_image,
            "table": self._render_table,
            "chart": self._render_chart,
            "card": self._render_card,
            "button": self._render_button,
            "link": self._render_link,
            "toggle": self._render_toggle,
            "row": self._render_row,
            "column": self._render_column,
            "grid": self._render_grid,
            "tab": self._render_tab,
            "map": self._render_map,
            "form": self._render_form,
            "dialog": self._render_dialog
        }
    
    def _register_default_handlers(self):
        """注册默认事件处理器"""
        self._event_handlers[EventType.COMPONENT_CLICK] = [self._handle_click]
        self._event_handlers[EventType.FORM_SUBMIT] = [self._handle_form_submit]
        self._event_handlers[EventType.VALUE_CHANGE] = [self._handle_value_change]
        self._event_handlers[EventType.FEEDBACK] = [self._handle_feedback]
    
    def convert_schema(self, schema) -> List[Dict[str, Any]]:
        """
        将UI Schema转换为前端可渲染格式
        
        Args:
            schema: DynamicUIEngine输出的Schema（支持LayoutSchema对象或字典）
        
        Returns:
            前端组件配置列表
        """
        if not schema:
            return []
        
        # 处理LayoutSchema对象
        if hasattr(schema, 'id') and hasattr(schema, 'components'):
            self._current_schema = {
                'id': schema.id,
                'type': schema.type,
                'components': schema.components
            }
            return self._convert_components(schema.components)
        
        # 处理字典格式
        if isinstance(schema, dict) and 'components' in schema:
            self._current_schema = schema
            return self._convert_components(schema['components'])
        
        return []
    
    def _convert_components(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """递归转换组件列表"""
        result = []
        
        for component in components:
            converted = self._convert_component(component)
            if converted:
                result.append(converted)
        
        return result
    
    def _convert_component(self, component) -> Optional[Dict[str, Any]]:
        """转换单个组件"""
        # 处理UIComponentSchema对象
        if hasattr(component, 'type') and hasattr(component, 'id'):
            # 将对象转换为字典
            component_dict = {
                'id': component.id,
                'type': component.type.value if hasattr(component.type, 'value') else str(component.type),
                'label': component.label,
                'placeholder': component.placeholder,
                'value': component.value,
                'required': component.required,
                'options': component.options,
                'validation': component.validation,
                'style': component.style,
                'children': component.children,
                'event_handlers': component.event_handlers,
                'context_rules': component.context_rules,
                'category': component.category.value if hasattr(component.category, 'value') else str(component.category)
            }
            component_type = component_dict['type']
        else:
            # 处理字典格式
            component_dict = component
            component_type = component.get('type')
        
        if not component_type or component_type not in self._component_renderers:
            logger.warning(f"未知组件类型: {component_type}")
            return None
        
        renderer = self._component_renderers[component_type]
        return renderer(component_dict)
    
    # ============ 组件渲染器 ============
    
    def _render_text_input(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "TextInput",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', ''),
                "placeholder": component.get('placeholder', ''),
                "value": component.get('value', ''),
                "required": component.get('required', False),
                "validation": component.get('validation', {})
            }
        }
    
    def _render_textarea(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "TextArea",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', ''),
                "placeholder": component.get('placeholder', ''),
                "value": component.get('value', ''),
                "rows": component.get('style', {}).get('rows', 4),
                "required": component.get('required', False)
            }
        }
    
    def _render_select(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Select",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', ''),
                "value": component.get('value', ''),
                "options": component.get('options', []),
                "required": component.get('required', False)
            }
        }
    
    def _render_multi_select(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "MultiSelect",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', ''),
                "value": component.get('value', []),
                "options": component.get('options', []),
                "required": component.get('required', False)
            }
        }
    
    def _render_checkbox(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Checkbox",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', ''),
                "checked": component.get('value', False),
                "required": component.get('required', False)
            }
        }
    
    def _render_radio(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "RadioGroup",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', ''),
                "value": component.get('value', ''),
                "options": component.get('options', []),
                "required": component.get('required', False)
            }
        }
    
    def _render_slider(self, component: Dict[str, Any]) -> Dict[str, Any]:
        options = component.get('options', {})
        return {
            "type": "Slider",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', ''),
                "value": component.get('value', 0),
                "min": options.get('min', 0),
                "max": options.get('max', 100),
                "step": options.get('step', 1),
                "required": component.get('required', False)
            }
        }
    
    def _render_date_picker(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "DatePicker",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', ''),
                "value": component.get('value', ''),
                "required": component.get('required', False)
            }
        }
    
    def _render_file_upload(self, component: Dict[str, Any]) -> Dict[str, Any]:
        if not component:
            return None
        options = component.get('options')
        # 处理options可能是列表或字典的情况
        if isinstance(options, dict):
            accept = options.get('accept', [])
        elif isinstance(options, list):
            accept = options
        else:
            accept = ['.pdf', '.docx', '.xlsx', '.jpg', '.png']
        
        return {
            "type": "FileUpload",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', '选择文件'),
                "accept": accept,
                "required": component.get('required', False)
            }
        }
    
    def _render_text(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Text",
            "props": {
                "id": component.get('id'),
                "content": component.get('value', ''),
                "style": component.get('style', {})
            }
        }
    
    def _render_heading(self, component: Dict[str, Any]) -> Dict[str, Any]:
        if not component:
            return None
        style = component.get('style') or {}
        return {
            "type": "Heading",
            "props": {
                "id": component.get('id'),
                "content": component.get('label', ''),
                "level": style.get('level', 2)
            }
        }
    
    def _render_image(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Image",
            "props": {
                "id": component.get('id'),
                "src": component.get('value', ''),
                "alt": component.get('label', ''),
                "style": component.get('style', {})
            }
        }
    
    def _render_table(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Table",
            "props": {
                "id": component.get('id'),
                "data": component.get('value', []),
                "columns": component.get('options', {}).get('columns', []),
                "style": component.get('style', {})
            }
        }
    
    def _render_chart(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Chart",
            "props": {
                "id": component.get('id'),
                "type": component.get('options', {}).get('type', 'bar'),
                "data": component.get('value', []),
                "title": component.get('label', '')
            }
        }
    
    def _render_card(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Card",
            "props": {
                "id": component.get('id'),
                "title": component.get('label', ''),
                "children": self._convert_components(component.get('children', []))
            }
        }
    
    def _render_button(self, component: Dict[str, Any]) -> Dict[str, Any]:
        if not component:
            return None
        style = component.get('style') or {}
        if style.get('primary'):
            variant = 'primary'
        elif style.get('secondary'):
            variant = 'secondary'
        else:
            variant = 'default'
        
        return {
            "type": "Button",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', ''),
                "variant": variant,
                "event": {"type": "click", "handler": "handle_button_click"}
            }
        }
    
    def _render_link(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Link",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', ''),
                "href": component.get('options', {}).get('href', '#'),
                "target": component.get('options', {}).get('target', '_self')
            }
        }
    
    def _render_toggle(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Toggle",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', ''),
                "checked": component.get('value', False),
                "event": {"type": "change", "handler": "handle_toggle_change"}
            }
        }
    
    def _render_row(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Row",
            "props": {
                "id": component.get('id'),
                "children": self._convert_components(component.get('children', []))
            }
        }
    
    def _render_column(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Column",
            "props": {
                "id": component.get('id'),
                "children": self._convert_components(component.get('children', []))
            }
        }
    
    def _render_grid(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Grid",
            "props": {
                "id": component.get('id'),
                "columns": component.get('options', {}).get('columns', 2),
                "children": self._convert_components(component.get('children', []))
            }
        }
    
    def _render_tab(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Tabs",
            "props": {
                "id": component.get('id'),
                "tabs": component.get('options', {}).get('tabs', []),
                "activeTab": component.get('value', 0)
            }
        }
    
    def _render_map(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Map",
            "props": {
                "id": component.get('id'),
                "label": component.get('label', ''),
                "center": component.get('options', {}).get('center', [32.0603, 118.7969]),
                "zoom": component.get('options', {}).get('zoom', 12),
                "markers": component.get('value', [])
            }
        }
    
    def _render_form(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Form",
            "props": {
                "id": component.get('id'),
                "title": component.get('label', ''),
                "children": self._convert_components(component.get('children', [])),
                "event": {"type": "submit", "handler": "handle_form_submit"}
            }
        }
    
    def _render_dialog(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "Dialog",
            "props": {
                "id": component.get('id'),
                "title": component.get('label', ''),
                "visible": component.get('value', False),
                "children": self._convert_components(component.get('children', [])),
                "event": {"type": "close", "handler": "handle_dialog_close"}
            }
        }
    
    # ============ 事件处理 ============
    
    def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理前端事件
        
        Args:
            event: 前端事件数据
        
        Returns:
            处理结果
        """
        try:
            event_type = EventType(event.get('event_type'))
            component_id = event.get('component_id')
            payload = event.get('payload', {})
            
            # 记录事件到进化学习服务
            self._record_to_learning_service(event_type, component_id, payload)
            
            # 调用事件处理器
            handlers = self._event_handlers.get(event_type, [])
            for handler in handlers:
                handler(component_id, payload)
            
            return {"success": True, "message": "事件处理成功"}
        
        except Exception as e:
            logger.error(f"事件处理失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _record_to_learning_service(self, event_type: EventType, component_id: str, payload: Dict[str, Any]):
        """记录事件到进化学习服务"""
        try:
            from business.evolutionary_learning import get_evolutionary_learning_service, BehaviorType
            
            service = get_evolutionary_learning_service()
            
            behavior_map = {
                EventType.COMPONENT_CLICK: BehaviorType.ACTION_EXECUTED,
                EventType.FORM_SUBMIT: BehaviorType.FORM_SUBMITTED,
                EventType.VALUE_CHANGE: BehaviorType.MESSAGE_SENT,
                EventType.FEEDBACK: BehaviorType.FEEDBACK_PROVIDED
            }
            
            behavior_type = behavior_map.get(event_type, BehaviorType.ACTION_EXECUTED)
            service.record_behavior(
                user_id="current_user",
                session_id="current_session",
                behavior_type=behavior_type,
                data={"component_id": component_id, **payload}
            )
            
        except ImportError:
            logger.warning("进化学习服务未加载")
        except Exception as e:
            logger.error(f"记录到学习服务失败: {e}")
    
    def _handle_click(self, component_id: str, payload: Dict[str, Any]):
        """处理点击事件"""
        logger.debug(f"组件点击: {component_id}")
    
    def _handle_form_submit(self, component_id: str, payload: Dict[str, Any]):
        """处理表单提交"""
        self._form_data[component_id] = payload
        logger.debug(f"表单提交: {component_id}, 数据: {payload}")
    
    def _handle_value_change(self, component_id: str, payload: Dict[str, Any]):
        """处理值变化"""
        logger.debug(f"值变化: {component_id} = {payload.get('value')}")
    
    def _handle_feedback(self, component_id: str, payload: Dict[str, Any]):
        """处理反馈"""
        # 记录奖励到动态UI引擎
        try:
            from business.dynamic_ui_engine import get_dynamic_ui_engine
            
            engine = get_dynamic_ui_engine()
            reward = 0.5 if payload.get('feedback') == 'helpful' else -0.3
            engine.record_reward(component_id, reward)
            
        except ImportError:
            logger.warning("动态UI引擎未加载")
    
    def register_event_handler(self, event_type: EventType, handler: Callable):
        """注册自定义事件处理器"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def get_form_data(self, form_id: Optional[str] = None) -> Dict[str, Any]:
        """获取表单数据"""
        if form_id:
            return self._form_data.get(form_id, {})
        return self._form_data
    
    def clear_form_data(self, form_id: Optional[str] = None):
        """清除表单数据"""
        if form_id:
            self._form_data.pop(form_id, None)
        else:
            self._form_data.clear()


# 全局单例
_global_ui_adapter: Optional[UIAdapter] = None


def get_ui_adapter() -> UIAdapter:
    """获取全局UI适配器单例"""
    global _global_ui_adapter
    if _global_ui_adapter is None:
        _global_ui_adapter = UIAdapter()
    return _global_ui_adapter


# 测试函数
def test_ui_adapter():
    """测试UI适配器"""
    print("🧪 测试UI适配器")
    print("="*60)
    
    adapter = get_ui_adapter()
    
    # 测试Schema转换
    print("\n📤 测试Schema转换")
    test_schema = {
        "id": "test_layout",
        "type": "vertical",
        "components": [
            {
                "id": "title",
                "type": "heading",
                "category": "display",
                "label": "测试表单"
            },
            {
                "id": "name",
                "type": "text_input",
                "category": "input",
                "label": "姓名",
                "placeholder": "请输入姓名",
                "required": True
            },
            {
                "id": "submit",
                "type": "button",
                "category": "action",
                "label": "提交",
                "style": {"primary": True}
            }
        ]
    }
    
    result = adapter.convert_schema(test_schema)
    print(f"   转换组件数量: {len(result)}")
    print(f"   第一个组件类型: {result[0]['type']}")
    print(f"   第二个组件类型: {result[1]['type']}")
    
    # 测试事件处理
    print("\n📝 测试事件处理")
    event = {
        "event_type": "component_click",
        "component_id": "submit",
        "payload": {"button_id": "submit"}
    }
    result = adapter.handle_event(event)
    print(f"   事件处理结果: {result['success']}")
    
    # 测试反馈事件
    print("\n🎯 测试反馈事件")
    feedback_event = {
        "event_type": "feedback",
        "component_id": "name",
        "payload": {"feedback": "helpful"}
    }
    result = adapter.handle_event(feedback_event)
    print(f"   反馈处理结果: {result['success']}")
    
    print("\n🎉 UI适配器测试完成！")
    return True


if __name__ == "__main__":
    test_ui_adapter()