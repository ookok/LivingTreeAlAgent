"""
Dynamic UI Engine - 动态UI渲染引擎

核心功能：
1. AI驱动的UI生成 - 根据上下文动态生成组件
2. 组件基因库 - 可进化的UI组件
3. 自适应布局 - 根据设备和上下文调整布局
4. 实时预览 - 支持实时UI预览

设计理念：
- UI不再由开发者写死，而是由AI根据上下文生成
- 组件可以通过强化学习进化
- 支持完整的组件生命周期管理
"""

import json
import uuid
from typing import Dict, Any, Optional, List, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ComponentCategory(Enum):
    """组件类别"""
    INPUT = "input"           # 输入类组件
    DISPLAY = "display"       # 展示类组件
    ACTION = "action"         # 操作类组件
    LAYOUT = "layout"         # 布局类组件
    SPECIAL = "special"       # 特殊组件（地图、图表等）


class ComponentType(Enum):
    """组件类型"""
    # 输入类
    TEXT_INPUT = "text_input"
    TEXTAREA = "textarea"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SLIDER = "slider"
    DATE_PICKER = "date_picker"
    FILE_UPLOAD = "file_upload"
    
    # 展示类
    TEXT = "text"
    HEADING = "heading"
    IMAGE = "image"
    TABLE = "table"
    CHART = "chart"
    CARD = "card"
    
    # 操作类
    BUTTON = "button"
    LINK = "link"
    TOGGLE = "toggle"
    
    # 布局类
    ROW = "row"
    COLUMN = "column"
    GRID = "grid"
    TAB = "tab"
    
    # 特殊类
    MAP = "map"
    FORM = "form"
    DIALOG = "dialog"


@dataclass
class UIComponentSchema:
    """UI组件Schema定义"""
    id: str
    type: ComponentType
    category: ComponentCategory
    label: Optional[str] = None
    placeholder: Optional[str] = None
    value: Optional[Any] = None
    required: bool = False
    options: Optional[List[Dict[str, Any]]] = None
    validation: Optional[Dict[str, Any]] = None
    style: Optional[Dict[str, Any]] = None
    children: Optional[List['UIComponentSchema']] = None
    event_handlers: Optional[Dict[str, str]] = None
    context_rules: Optional[List[Dict[str, Any]]] = None  # 何时显示该组件的规则


@dataclass
class ComponentGene:
    """组件基因 - 记录组件的进化信息"""
    component_id: str
    type: ComponentType
    usage_count: int = 0
    success_rate: float = 0.5
    last_used: Optional[datetime] = None
    contexts: List[Dict[str, Any]] = field(default_factory=list)  # 使用过的上下文
    rewards: List[float] = field(default_factory=list)  # 获得的奖励


@dataclass
class LayoutSchema:
    """布局Schema"""
    id: str
    type: str  # vertical, horizontal, grid, tabs
    components: List[UIComponentSchema] = field(default_factory=list)
    style: Optional[Dict[str, Any]] = None


class DynamicUIEngine:
    """
    动态UI引擎
    
    核心特性：
    1. AI驱动的UI生成 - 根据上下文动态生成组件
    2. 组件基因库 - 可进化的UI组件
    3. 自适应布局 - 根据设备和上下文调整布局
    4. 强化学习优化 - 根据用户反馈优化组件选择
    """
    
    def __init__(self):
        # 组件基因库
        self._component_genes: Dict[str, ComponentGene] = self._init_component_genes()
        
        # 当前渲染的UI
        self._current_ui: Optional[LayoutSchema] = None
        
        # 上下文历史
        self._context_history: List[Dict[str, Any]] = []
        
        # 奖励累计
        self._total_reward = 0.0
        
        logger.info("✅ DynamicUIEngine 初始化完成")
    
    def _init_component_genes(self) -> Dict[str, ComponentGene]:
        """初始化组件基因库"""
        genes = {}
        
        for component_type in ComponentType:
            # 确定类别
            if component_type.value in ['text_input', 'textarea', 'select', 'multi_select', 
                                       'checkbox', 'radio', 'slider', 'date_picker', 'file_upload']:
                category = ComponentCategory.INPUT
            elif component_type.value in ['text', 'heading', 'image', 'table', 'chart', 'card']:
                category = ComponentCategory.DISPLAY
            elif component_type.value in ['button', 'link', 'toggle']:
                category = ComponentCategory.ACTION
            elif component_type.value in ['row', 'column', 'grid', 'tab']:
                category = ComponentCategory.LAYOUT
            else:
                category = ComponentCategory.SPECIAL
            
            genes[component_type.value] = ComponentGene(
                component_id=component_type.value,
                type=component_type
            )
        
        return genes
    
    def generate_ui(self, context: Dict[str, Any]) -> LayoutSchema:
        """
        根据上下文生成完整的UI布局
        
        Args:
            context: 当前上下文（包含用户输入、对话历史、知识等）
        
        Returns:
            布局Schema
        """
        # 保存上下文历史
        self._context_history.append(context)
        
        # 分析上下文
        analysis = self._analyze_context(context)
        
        # 根据分析结果生成UI
        layout = self._generate_layout(analysis)
        
        # 更新组件使用统计
        self._update_component_usage(layout)
        
        self._current_ui = layout
        return layout
    
    def _analyze_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """分析上下文，提取关键信息"""
        analysis = {
            "intent": self._detect_intent(context),
            "entities": self._extract_entities(context),
            "context_type": self._classify_context(context),
            "complexity": self._calculate_complexity(context),
            "previous_interactions": self._get_previous_interactions(context)
        }
        return analysis
    
    def _detect_intent(self, context: Dict[str, Any]) -> str:
        """检测用户意图"""
        text = context.get('text', '').lower()
        
        if any(k in text for k in ['上传', '文件', '导入']):
            return 'upload'
        if any(k in text for k in ['填写', '输入', '表单']):
            return 'form_fill'
        if any(k in text for k in ['地图', '位置', '坐标', '标绘']):
            return 'map_interaction'
        if any(k in text for k in ['报告', '生成', '导出']):
            return 'report_generation'
        if any(k in text for k in ['查询', '检索', '查找']):
            return 'search'
        if any(k in text for k in ['分析', '评估', '计算']):
            return 'analysis'
        
        return 'general'
    
    def _extract_entities(self, context: Dict[str, Any]) -> List[str]:
        """提取实体"""
        text = context.get('text', '')
        
        entities = []
        env_entities = [
            '化工', '水源地', '敏感区', '噪声', '大气', '水环境',
            '监测', '预测', '导则', '标准', '项目', '污染'
        ]
        
        for entity in env_entities:
            if entity in text:
                entities.append(entity)
        
        return entities
    
    def _classify_context(self, context: Dict[str, Any]) -> str:
        """分类上下文类型"""
        intent = self._detect_intent(context)
        
        if intent in ['upload', 'form_fill']:
            return 'data_entry'
        elif intent == 'map_interaction':
            return 'visualization'
        elif intent == 'report_generation':
            return 'document'
        elif intent == 'search':
            return 'information_retrieval'
        else:
            return 'conversation'
    
    def _calculate_complexity(self, context: Dict[str, Any]) -> int:
        """计算上下文复杂度"""
        text = context.get('text', '')
        entities = self._extract_entities(context)
        
        complexity = 0
        
        # 基于长度
        if len(text) > 100:
            complexity += 1
        if len(text) > 300:
            complexity += 1
        
        # 基于实体数量
        if len(entities) >= 2:
            complexity += 1
        if len(entities) >= 4:
            complexity += 1
        
        # 基于意图
        intent = self._detect_intent(context)
        if intent in ['analysis', 'report_generation']:
            complexity += 1
        
        return min(complexity, 5)
    
    def _get_previous_interactions(self, context: Dict[str, Any]) -> List[str]:
        """获取之前的交互历史"""
        return context.get('history', [])[:5]  # 最近5次交互
    
    def _generate_layout(self, analysis: Dict[str, Any]) -> LayoutSchema:
        """根据分析结果生成布局"""
        layout_id = f"layout_{str(uuid.uuid4())[:8]}"
        components = []
        
        intent = analysis['intent']
        context_type = analysis['context_type']
        
        # 根据意图生成组件
        if intent == 'upload':
            components = self._generate_upload_ui(analysis)
        elif intent == 'form_fill':
            components = self._generate_form_ui(analysis)
        elif intent == 'map_interaction':
            components = self._generate_map_ui(analysis)
        elif intent == 'report_generation':
            components = self._generate_report_ui(analysis)
        elif intent == 'search':
            components = self._generate_search_ui(analysis)
        elif intent == 'analysis':
            components = self._generate_analysis_ui(analysis)
        else:
            components = self._generate_default_ui(analysis)
        
        # 添加通用组件
        components.append(self._generate_action_buttons())
        
        return LayoutSchema(
            id=layout_id,
            type='vertical',
            components=components
        )
    
    def _generate_upload_ui(self, analysis: Dict[str, Any]) -> List[UIComponentSchema]:
        """生成文件上传UI"""
        return [
            UIComponentSchema(
                id="upload_title",
                type=ComponentType.HEADING,
                category=ComponentCategory.DISPLAY,
                label="上传文件"
            ),
            UIComponentSchema(
                id="upload_desc",
                type=ComponentType.TEXT,
                category=ComponentCategory.DISPLAY,
                value="请上传环评相关文件（支持 PDF、DOCX、XLSX、JPG、PNG、CAD）"
            ),
            UIComponentSchema(
                id="file_upload",
                type=ComponentType.FILE_UPLOAD,
                category=ComponentCategory.INPUT,
                label="选择文件",
                options=[{"accept": [".pdf", ".docx", ".xlsx", ".jpg", ".png"]}]
            ),
            UIComponentSchema(
                id="upload_note",
                type=ComponentType.TEXT,
                category=ComponentCategory.DISPLAY,
                value="上传的文件将自动解析并关联到项目"
            )
        ]
    
    def _generate_form_ui(self, analysis: Dict[str, Any]) -> List[UIComponentSchema]:
        """生成表单UI"""
        entities = analysis.get('entities', [])
        complexity = analysis.get('complexity', 1)
        
        fields = []
        
        # 根据实体动态生成字段
        if '项目' in entities:
            fields.append(UIComponentSchema(
                id="project_name",
                type=ComponentType.TEXT_INPUT,
                category=ComponentCategory.INPUT,
                label="项目名称",
                placeholder="请输入项目名称",
                required=True
            ))
        
        if '化工' in entities or '污染' in entities:
            fields.append(UIComponentSchema(
                id="project_type",
                type=ComponentType.SELECT,
                category=ComponentCategory.INPUT,
                label="项目类型",
                options=[
                    {"value": "chemical", "label": "化工项目"},
                    {"value": "manufacturing", "label": "制造业项目"},
                    {"value": "infrastructure", "label": "基础设施项目"},
                    {"value": "other", "label": "其他"}
                ],
                required=True
            ))
        
        if '水源地' in entities or '敏感区' in entities:
            fields.append(UIComponentSchema(
                id="sensitive_area",
                type=ComponentType.MULTI_SELECT,
                category=ComponentCategory.INPUT,
                label="涉及敏感区域",
                options=[
                    {"value": "water_source", "label": "水源地"},
                    {"value": "residential", "label": "居民区"},
                    {"value": "school", "label": "学校"},
                    {"value": "hospital", "label": "医院"},
                    {"value": "nature_reserve", "label": "自然保护区"}
                ]
            ))
        
        if complexity >= 3:
            fields.append(UIComponentSchema(
                id="description",
                type=ComponentType.TEXTAREA,
                category=ComponentCategory.INPUT,
                label="项目描述",
                placeholder="请详细描述项目情况...",
                style={"rows": 4}
            ))
        
        return [
            UIComponentSchema(
                id="form_title",
                type=ComponentType.HEADING,
                category=ComponentCategory.DISPLAY,
                label="补充信息"
            )
        ] + fields
    
    def _generate_map_ui(self, analysis: Dict[str, Any]) -> List[UIComponentSchema]:
        """生成地图交互UI"""
        return [
            UIComponentSchema(
                id="map_title",
                type=ComponentType.HEADING,
                category=ComponentCategory.DISPLAY,
                label="地图标绘"
            ),
            UIComponentSchema(
                id="map_desc",
                type=ComponentType.TEXT,
                category=ComponentCategory.DISPLAY,
                value="请在地图上进行标绘操作"
            ),
            UIComponentSchema(
                id="coordinates_input",
                type=ComponentType.TEXT_INPUT,
                category=ComponentCategory.INPUT,
                label="中心点坐标",
                placeholder="例如：32.0603, 118.7969"
            ),
            UIComponentSchema(
                id="radius_slider",
                type=ComponentType.SLIDER,
                category=ComponentCategory.INPUT,
                label="影响半径(km)",
                options=[{"min": 1, "max": 10, "step": 1}]
            ),
            UIComponentSchema(
                id="map_canvas",
                type=ComponentType.MAP,
                category=ComponentCategory.SPECIAL,
                label="地图"
            )
        ]
    
    def _generate_report_ui(self, analysis: Dict[str, Any]) -> List[UIComponentSchema]:
        """生成报告生成UI"""
        return [
            UIComponentSchema(
                id="report_title",
                type=ComponentType.HEADING,
                category=ComponentCategory.DISPLAY,
                label="生成报告"
            ),
            UIComponentSchema(
                id="report_type",
                type=ComponentType.SELECT,
                category=ComponentCategory.INPUT,
                label="报告类型",
                options=[
                    {"value": "full", "label": "完整报告"},
                    {"value": "summary", "label": "报告摘要"},
                    {"value": "specific", "label": "特定章节"}
                ],
                required=True
            ),
            UIComponentSchema(
                id="include_sections",
                type=ComponentType.MULTI_SELECT,
                category=ComponentCategory.INPUT,
                label="包含章节",
                options=[
                    {"value": "overview", "label": "项目概述"},
                    {"value": "现状", "label": "现状调查"},
                    {"value": "prediction", "label": "影响预测"},
                    {"value": "measures", "label": "环保措施"},
                    {"value": "conclusion", "label": "结论与建议"}
                ]
            ),
            UIComponentSchema(
                id="format_select",
                type=ComponentType.SELECT,
                category=ComponentCategory.INPUT,
                label="输出格式",
                options=[
                    {"value": "markdown", "label": "Markdown"},
                    {"value": "word", "label": "Word"},
                    {"value": "pdf", "label": "PDF"}
                ]
            )
        ]
    
    def _generate_search_ui(self, analysis: Dict[str, Any]) -> List[UIComponentSchema]:
        """生成搜索UI"""
        entities = analysis.get('entities', [])
        
        return [
            UIComponentSchema(
                id="search_title",
                type=ComponentType.HEADING,
                category=ComponentCategory.DISPLAY,
                label="知识检索"
            ),
            UIComponentSchema(
                id="search_input",
                type=ComponentType.TEXT_INPUT,
                category=ComponentCategory.INPUT,
                label="搜索关键词",
                placeholder="输入搜索关键词...",
                value=", ".join(entities) if entities else ""
            ),
            UIComponentSchema(
                id="search_type",
                type=ComponentType.SELECT,
                category=ComponentCategory.INPUT,
                label="搜索范围",
                options=[
                    {"value": "all", "label": "全部"},
                    {"value": "guide", "label": "导则标准"},
                    {"value": "report", "label": "报告范本"},
                    {"value": "regulation", "label": "法律法规"}
                ]
            ),
            UIComponentSchema(
                id="quick_search",
                type=ComponentType.TEXT,
                category=ComponentCategory.DISPLAY,
                value="快速搜索：" + ", ".join([f"「{e}」" for e in entities][:3]) if entities else ""
            )
        ]
    
    def _generate_analysis_ui(self, analysis: Dict[str, Any]) -> List[UIComponentSchema]:
        """生成分析UI"""
        return [
            UIComponentSchema(
                id="analysis_title",
                type=ComponentType.HEADING,
                category=ComponentCategory.DISPLAY,
                label="数据分析"
            ),
            UIComponentSchema(
                id="analysis_type",
                type=ComponentType.SELECT,
                category=ComponentCategory.INPUT,
                label="分析类型",
                options=[
                    {"value": "impact", "label": "环境影响分析"},
                    {"value": "compliance", "label": "合规性分析"},
                    {"value": "risk", "label": "风险评估"},
                    {"value": "comparison", "label": "对比分析"}
                ],
                required=True
            ),
            UIComponentSchema(
                id="data_source",
                type=ComponentType.MULTI_SELECT,
                category=ComponentCategory.INPUT,
                label="数据源",
                options=[
                    {"value": "monitoring", "label": "监测数据"},
                    {"value": "standard", "label": "标准限值"},
                    {"value": "baseline", "label": "现状基线"},
                    {"value": "prediction", "label": "预测结果"}
                ]
            ),
            UIComponentSchema(
                id="chart_display",
                type=ComponentType.CHART,
                category=ComponentCategory.DISPLAY,
                label="分析结果图表"
            )
        ]
    
    def _generate_default_ui(self, analysis: Dict[str, Any]) -> List[UIComponentSchema]:
        """生成默认UI"""
        return [
            UIComponentSchema(
                id="default_prompt",
                type=ComponentType.TEXT,
                category=ComponentCategory.DISPLAY,
                value="请问您需要我帮您做什么？"
            ),
            UIComponentSchema(
                id="quick_actions",
                type=ComponentType.TEXT,
                category=ComponentCategory.DISPLAY,
                value="快捷操作：上传文件 | 填写表单 | 检索知识 | 生成报告"
            )
        ]
    
    def _generate_action_buttons(self) -> UIComponentSchema:
        """生成操作按钮"""
        return UIComponentSchema(
            id="action_buttons",
            type=ComponentType.ROW,
            category=ComponentCategory.LAYOUT,
            children=[
                UIComponentSchema(
                    id="btn_submit",
                    type=ComponentType.BUTTON,
                    category=ComponentCategory.ACTION,
                    label="提交",
                    style={"primary": True}
                ),
                UIComponentSchema(
                    id="btn_reset",
                    type=ComponentType.BUTTON,
                    category=ComponentCategory.ACTION,
                    label="重置"
                ),
                UIComponentSchema(
                    id="btn_cancel",
                    type=ComponentType.BUTTON,
                    category=ComponentCategory.ACTION,
                    label="取消",
                    style={"secondary": True}
                )
            ]
        )
    
    def _update_component_usage(self, layout: LayoutSchema):
        """更新组件使用统计"""
        def update_usage(components: List[UIComponentSchema]):
            for component in components:
                gene = self._component_genes.get(component.type.value)
                if gene:
                    gene.usage_count += 1
                    gene.last_used = datetime.now()
                    gene.contexts.append({"type": component.type.value, "timestamp": datetime.now().isoformat()})
                
                # 递归处理子组件
                if component.children:
                    update_usage(component.children)
        
        update_usage(layout.components)
    
    def record_reward(self, component_id: str, reward: float):
        """
        记录组件奖励
        
        Args:
            component_id: 组件ID
            reward: 奖励值（-1到1）
        """
        gene = self._component_genes.get(component_id)
        if gene:
            gene.rewards.append(reward)
            # 更新成功率
            if gene.rewards:
                positive_rewards = sum(1 for r in gene.rewards if r > 0)
                gene.success_rate = positive_rewards / len(gene.rewards)
        
        self._total_reward += reward
    
    def get_component_gene(self, component_type: str) -> Optional[ComponentGene]:
        """获取组件基因"""
        return self._component_genes.get(component_type)
    
    def get_component_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有组件统计"""
        stats = {}
        for component_id, gene in self._component_genes.items():
            stats[component_id] = {
                "usage_count": gene.usage_count,
                "success_rate": round(gene.success_rate, 2),
                "last_used": gene.last_used.isoformat() if gene.last_used else None,
                "reward_count": len(gene.rewards),
                "avg_reward": round(sum(gene.rewards) / max(len(gene.rewards), 1), 2)
            }
        return stats
    
    def suggest_components(self, context: Dict[str, Any]) -> List[str]:
        """
        根据上下文推荐组件
        
        Args:
            context: 当前上下文
        
        Returns:
            推荐的组件类型列表（按优先级排序）
        """
        intent = self._detect_intent(context)
        entities = self._extract_entities(context)
        complexity = self._calculate_complexity(context)
        
        suggestions = []
        
        # 基于意图推荐
        if intent == 'upload':
            suggestions.append('file_upload')
        elif intent == 'form_fill':
            suggestions.extend(['text_input', 'select', 'textarea'])
        elif intent == 'map_interaction':
            suggestions.extend(['map', 'text_input', 'slider'])
        elif intent == 'report_generation':
            suggestions.extend(['select', 'multi_select', 'button'])
        elif intent == 'search':
            suggestions.extend(['text_input', 'select'])
        elif intent == 'analysis':
            suggestions.extend(['select', 'multi_select', 'chart'])
        
        # 基于实体推荐
        if len(entities) >= 2:
            suggestions.append('multi_select')
        
        # 基于复杂度推荐
        if complexity >= 3:
            suggestions.append('textarea')
        
        return suggestions
    
    def export_ui_schema(self, layout: Optional[LayoutSchema] = None) -> str:
        """导出UI Schema为JSON"""
        target_layout = layout or self._current_ui
        if not target_layout:
            return json.dumps({"error": "No UI to export"})
        
        def serialize_component(component: UIComponentSchema) -> Dict[str, Any]:
            data = {
                "id": component.id,
                "type": component.type.value,
                "category": component.category.value
            }
            
            if component.label:
                data["label"] = component.label
            if component.placeholder:
                data["placeholder"] = component.placeholder
            if component.value:
                data["value"] = component.value
            if component.required:
                data["required"] = component.required
            if component.options:
                data["options"] = component.options
            if component.validation:
                data["validation"] = component.validation
            if component.style:
                data["style"] = component.style
            if component.children:
                data["children"] = [serialize_component(c) for c in component.children]
            
            return data
        
        return json.dumps({
            "id": target_layout.id,
            "type": target_layout.type,
            "components": [serialize_component(c) for c in target_layout.components]
        }, indent=2, ensure_ascii=False)


# 全局单例
_global_dynamic_ui_engine: Optional[DynamicUIEngine] = None


def get_dynamic_ui_engine() -> DynamicUIEngine:
    """获取全局动态UI引擎单例"""
    global _global_dynamic_ui_engine
    if _global_dynamic_ui_engine is None:
        _global_dynamic_ui_engine = DynamicUIEngine()
    return _global_dynamic_ui_engine


# 测试函数
def test_dynamic_ui_engine():
    """测试动态UI引擎"""
    print("🧪 测试动态UI引擎")
    print("="*60)
    
    engine = get_dynamic_ui_engine()
    
    # 测试1: 上传意图
    print("\n📤 测试1: 上传意图")
    context1 = {"text": "我要上传监测数据Excel文件"}
    layout1 = engine.generate_ui(context1)
    print(f"   生成布局ID: {layout1.id}")
    print(f"   组件数量: {len(layout1.components)}")
    print(f"   第一个组件: {layout1.components[0].type.value}")
    
    # 测试2: 表单填写意图
    print("\n📝 测试2: 表单填写意图")
    context2 = {"text": "我要填写项目基本信息，这是一个化工项目，位于水源地附近"}
    layout2 = engine.generate_ui(context2)
    print(f"   生成布局ID: {layout2.id}")
    print(f"   组件数量: {len(layout2.components)}")
    
    # 测试3: 地图交互意图
    print("\n🗺️ 测试3: 地图交互意图")
    context3 = {"text": "在地图上标绘敏感区域"}
    layout3 = engine.generate_ui(context3)
    print(f"   生成布局ID: {layout3.id}")
    
    # 测试4: 组件推荐
    print("\n🔧 测试4: 组件推荐")
    suggestions = engine.suggest_components({"text": "填写监测数据表单"})
    print(f"   推荐组件: {suggestions}")
    
    # 测试5: 记录奖励
    print("\n🎯 测试5: 记录奖励")
    engine.record_reward("text_input", 0.8)
    engine.record_reward("select", -0.2)
    engine.record_reward("button", 0.5)
    
    # 测试6: 获取组件统计
    print("\n📊 测试6: 组件统计")
    stats = engine.get_component_stats()
    active_components = {k: v for k, v in stats.items() if v["usage_count"] > 0}
    print(f"   活跃组件数量: {len(active_components)}")
    for comp_id, stat in active_components.items():
        print(f"   {comp_id}: 使用{stat['usage_count']}次, 成功率{stat['success_rate']}")
    
    # 测试7: 导出Schema
    print("\n📤 测试7: 导出Schema")
    schema = engine.export_ui_schema(layout1)
    print(f"   Schema长度: {len(schema)} 字符")
    
    print("\n🎉 动态UI引擎测试完成！")
    return True


if __name__ == "__main__":
    test_dynamic_ui_engine()