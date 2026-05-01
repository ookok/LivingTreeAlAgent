"""
行动层（Action Layer）：动态UI作为"可进化"的器官

核心功能：
1. UI as Learned Behavior：由AI根据上下文动态组装交互元素
2. 组件基因库：基础UI组件库，由AI决定何时使用
3. 动态UI渲染引擎
"""

import json
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum

class ComponentType(Enum):
    TEXT_INPUT = 'text_input'
    TEXTAREA = 'textarea'
    FILE_UPLOAD = 'file_upload'
    TABLE = 'table'
    MAP = 'map'
    SELECT = 'select'
    CHECKBOX = 'checkbox'
    BUTTON = 'button'
    CHART = 'chart'
    FORM = 'form'
    SECTION = 'section'

@dataclass
class UIComponent:
    component_id: str
    type: ComponentType
    label: str = ""
    placeholder: str = ""
    options: List[Dict[str, Any]] = None
    data: List[Dict[str, Any]] = None
    required: bool = False
    visible: bool = True
    weight: float = 1.0  # 组件优先级权重

@dataclass
class RenderSchema:
    schema_id: str
    components: List[UIComponent]
    layout: str = 'vertical'  # vertical, horizontal, grid
    title: str = ""

class ComponentGenePool:
    """组件基因库：维护基础UI组件及其使用策略"""
    
    def __init__(self):
        self.component_stats: Dict[str, Dict[str, int]] = {}  # 组件使用统计
        self.preferred_components: Dict[str, List[str]] = {}  # 场景到组件的映射
    
    def record_usage(self, context_type: str, component_type: str, success: bool = True):
        """
        记录组件使用情况
        
        Args:
            context_type: 上下文类型，如 'monitoring_data', 'sensitive_area', 'report_section'
            component_type: 组件类型
            success: 是否成功（用户是否使用了该组件）
        """
        if context_type not in self.component_stats:
            self.component_stats[context_type] = {}
        
        if component_type not in self.component_stats[context_type]:
            self.component_stats[context_type][component_type] = {'used': 0, 'success': 0}
        
        self.component_stats[context_type][component_type]['used'] += 1
        if success:
            self.component_stats[context_type][component_type]['success'] += 1
        
        self._update_preferences()
    
    def _update_preferences(self):
        """根据使用统计更新组件偏好"""
        for context_type, stats in self.component_stats.items():
            # 计算成功率并排序
            success_rates = []
            for comp_type, counts in stats.items():
                rate = counts['success'] / counts['used'] if counts['used'] > 0 else 0
                success_rates.append((comp_type, rate))
            
            # 按成功率排序
            success_rates.sort(key=lambda x: x[1], reverse=True)
            self.preferred_components[context_type] = [comp for comp, _ in success_rates]
    
    def get_preferred_components(self, context_type: str) -> List[str]:
        """获取指定上下文的首选组件列表"""
        return self.preferred_components.get(context_type, [])

class ActionLayer:
    def __init__(self):
        self.gene_pool = ComponentGenePool()
        self.render_history = []
        self.schema_counter = 0
    
    def generate_ui_schema(self, context: Dict[str, Any]) -> RenderSchema:
        """
        根据当前上下文动态生成UI Schema
        
        进化示例：
        - AI发现用户总是通过"上传Excel"来提供监测数据，
          那么下次遇到类似场景，它会优先渲染"文件上传"组件
        """
        components = []
        
        # 分析上下文，决定使用哪些组件
        context_type = self._classify_context(context)
        preferred_components = self.gene_pool.get_preferred_components(context_type)
        
        # 如果有偏好的组件，优先使用
        if preferred_components:
            components = self._build_from_preferences(context_type, preferred_components)
        else:
            # 默认策略：根据上下文特征选择组件
            components = self._build_default_schema(context)
        
        schema = RenderSchema(
            schema_id=f"schema_{self.schema_counter}",
            components=components,
            title=self._generate_title(context),
            layout='vertical'
        )
        
        self.schema_counter += 1
        self.render_history.append({
            'schema_id': schema.schema_id,
            'context_type': context_type,
            'components': [c.type.value for c in components]
        })
        
        return schema
    
    def _classify_context(self, context: Dict[str, Any]) -> str:
        """分类当前上下文类型"""
        text = context.get('text_content', '')
        
        if '监测数据' in text or 'Excel' in text or '表格' in text:
            return 'monitoring_data'
        elif '坐标' in text or '地图' in text or '敏感区' in text:
            return 'geo_data'
        elif '报告' in text or '章节' in text or '内容' in text:
            return 'report_section'
        elif '图纸' in text or 'CAD' in text:
            return 'cad_drawing'
        else:
            return 'general'
    
    def _build_from_preferences(self, context_type: str, preferred_components: List[str]) -> List[UIComponent]:
        """根据学习到的偏好构建组件"""
        components = []
        
        for comp_type in preferred_components[:3]:
            component = self._create_component(comp_type, context_type)
            if component:
                components.append(component)
        
        return components
    
    def _build_default_schema(self, context: Dict[str, Any]) -> List[UIComponent]:
        """构建默认UI Schema"""
        components = []
        
        # 根据上下文特征决定组件
        if context.get('has_tabular_data', False):
            components.append(UIComponent(
                component_id='table_1',
                type=ComponentType.TABLE,
                label='监测数据表格',
                data=context.get('tabular_data', [])
            ))
        
        if context.get('has_files', False):
            components.append(UIComponent(
                component_id='upload_1',
                type=ComponentType.FILE_UPLOAD,
                label='上传文件',
                placeholder='点击或拖拽上传文件'
            ))
        
        if context.get('has_geo_data', False):
            components.append(UIComponent(
                component_id='map_1',
                type=ComponentType.MAP,
                label='地图标绘'
            ))
        
        # 默认添加文本输入
        components.append(UIComponent(
            component_id='input_1',
            type=ComponentType.TEXTAREA,
            label='输入内容',
            placeholder='请输入相关信息...'
        ))
        
        return components
    
    def _create_component(self, comp_type: str, context_type: str) -> UIComponent:
        """根据类型创建组件"""
        component_map = {
            'text_input': UIComponent(
                component_id=f"comp_{comp_type}",
                type=ComponentType.TEXT_INPUT,
                label='文本输入',
                placeholder='请输入...'
            ),
            'textarea': UIComponent(
                component_id=f"comp_{comp_type}",
                type=ComponentType.TEXTAREA,
                label='多行输入',
                placeholder='请输入详细内容...'
            ),
            'file_upload': UIComponent(
                component_id=f"comp_{comp_type}",
                type=ComponentType.FILE_UPLOAD,
                label='上传文件',
                placeholder='点击或拖拽上传'
            ),
            'table': UIComponent(
                component_id=f"comp_{comp_type}",
                type=ComponentType.TABLE,
                label='数据表格',
                data=[]
            ),
            'map': UIComponent(
                component_id=f"comp_{comp_type}",
                type=ComponentType.MAP,
                label='地图'
            ),
            'select': UIComponent(
                component_id=f"comp_{comp_type}",
                type=ComponentType.SELECT,
                label='选择',
                options=[
                    {'value': 'option1', 'label': '选项1'},
                    {'value': 'option2', 'label': '选项2'}
                ]
            )
        }
        
        return component_map.get(comp_type)
    
    def _generate_title(self, context: Dict[str, Any]) -> str:
        """生成合适的标题"""
        text = context.get('text_content', '')
        
        if '监测' in text:
            return '监测数据录入'
        elif '地图' in text:
            return '空间数据标绘'
        elif '报告' in text:
            return '报告章节编辑'
        else:
            return '交互面板'
    
    def record_interaction(self, schema_id: str, component_id: str, action: str):
        """
        记录用户与组件的交互
        
        Args:
            schema_id: 渲染的Schema ID
            component_id: 用户交互的组件ID
            action: 交互类型，如 'submit', 'upload', 'select', 'edit'
        """
        # 从历史中找到对应的上下文类型
        for record in reversed(self.render_history):
            if record['schema_id'] == schema_id:
                context_type = record['context_type']
                # 查找组件类型
                for comp_type in record['components']:
                    if comp_type in component_id.lower():
                        self.gene_pool.record_usage(context_type, comp_type, success=True)
                break
    
    def export_ui_stats(self) -> Dict[str, Any]:
        """导出UI使用统计用于分析"""
        return {
            'component_stats': self.gene_pool.component_stats,
            'preferred_components': self.gene_pool.preferred_components,
            'render_history': self.render_history
        }