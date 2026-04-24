# -*- coding: utf-8 -*-
"""
交互式资料收集器 - Interactive Data Collector
==============================================

功能：
1. 对话式引导用户收集资料
2. 地图位置选择生成坐标
3. 文件上传解析（平面图、草图等）
4. 半自动化数据补全
5. UI面板选择项集成

复用模块：
- WritingDataCollector (数据采集)
- DocumentAnalyzer (文档分析)

Author: Hermes Desktop Team
"""

import logging
import json
import re
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class CollectionType(Enum):
    """收集类型"""
    LOCATION = "location"           # 地理位置
    MAP_SELECTION = "map_selection" # 地图选点
    FILE_UPLOAD = "file_upload"     # 文件上传
    TEXT_INPUT = "text_input"       # 文本输入
    SELECT_CHOICE = "select_choice" # 选择项
    MULTI_CHOICE = "multi_choice"   # 多选
    DATE_PICKER = "date_picker"     # 日期选择
    NUMBER_INPUT = "number_input"   # 数字输入
    RANGE_SLIDER = "range_slider"   # 范围滑块
    IMAGE_UPLOAD = "image_upload"   # 图片上传


@dataclass
class CollectionItem:
    """收集项"""
    id: str
    field: str
    label: str
    type: CollectionType
    hint: str = ""
    required: bool = True
    default_value: Any = None
    options: Optional[List[str]] = None  # 选择选项
    min_value: Optional[float] = None     # 数字/范围最小值
    max_value: Optional[float] = None     # 数字/范围最大值
    unit: Optional[str] = None            # 单位
    depends_on: Optional[str] = None     # 依赖字段
    auto_collect: bool = True             # 是否自动采集
    ai_suggest: Optional[str] = None     # AI建议值


@dataclass
class CollectionResult:
    """收集结果"""
    item_id: str
    field: str
    value: Any
    source: str  # "user_input", "auto_collected", "ai_suggestion"
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionSession:
    """收集会话"""
    id: str
    doc_type: str
    items: List[CollectionItem]
    results: Dict[str, CollectionResult] = field(default_factory=dict)
    completed: List[str] = field(default_factory=list)
    pending: List[str] = field(default_factory=list)
    stage: str = "initial"
    auto_collected_count: int = 0
    user_input_count: int = 0
    
    def get_pending_items(self) -> List[CollectionItem]:
        return [i for i in self.items if i.id not in self.completed]
    
    def get_completion_rate(self) -> float:
        if not self.items:
            return 1.0
        return len(self.completed) / len(self.items)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "doc_type": self.doc_type,
            "total_items": len(self.items),
            "completed": len(self.completed),
            "pending": len(self.pending),
            "completion_rate": self.get_completion_rate(),
            "auto_collected": self.auto_collected_count,
            "user_inputs": self.user_input_count,
            "stage": self.stage,
            "results": {k: v.value for k, v in self.results.items()},
        }


class InteractiveCollector:
    """
    交互式资料收集器
    
    使用示例：
    ```python
    collector = InteractiveCollector()
    
    # 开始收集会话
    session = collector.start_session(doc_type="eia_report", industry="化工")
    
    # 获取下一个需要收集的项
    item = collector.get_next_item(session)
    
    # 用户选择/输入
    session = collector.submit(session, item.id, value="xxx")
    
    # 完成并获取结果
    results = collector.complete_session(session)
    ```
    """
    
    def __init__(self):
        self._sessions: Dict[str, CollectionSession] = {}
        self._data_collector = None
        self._doc_analyzer = None
        
    @property
    def data_collector(self):
        """延迟加载数据采集器"""
        if self._data_collector is None:
            try:
                from core.smart_writing.data_collector import get_data_collector
                self._data_collector = get_data_collector()
            except ImportError:
                logger.warning("WritingDataCollector 未安装")
        return self._data_collector
    
    @property
    def doc_analyzer(self):
        """延迟加载文档分析器"""
        if self._doc_analyzer is None:
            try:
                from core.smart_writing.document_analyzer import get_document_analyzer
                self._doc_analyzer = get_document_analyzer()
            except ImportError:
                logger.warning("DocumentAnalyzer 未安装")
        return self._doc_analyzer
    
    def start_session(
        self,
        doc_type: str,
        industry: Optional[str] = None,
        requirement: str = "",
        auto_collect: bool = True
    ) -> CollectionSession:
        """
        开始收集会话
        
        Args:
            doc_type: 文档类型
            industry: 行业类型
            requirement: 需求描述
            auto_collect: 是否自动采集
        
        Returns:
            CollectionSession: 收集会话
        """
        import uuid
        
        session_id = uuid.uuid4().hex[:8]
        
        # 根据文档类型和行业生成收集项
        items = self._generate_collection_items(doc_type, industry, requirement)
        
        session = CollectionSession(
            id=session_id,
            doc_type=doc_type,
            items=items,
            pending=[i.id for i in items if i.required],
        )
        
        # 自动采集
        if auto_collect:
            session = self._auto_collect(session, requirement)
        
        self._sessions[session_id] = session
        return session
    
    def _generate_collection_items(
        self,
        doc_type: str,
        industry: Optional[str],
        requirement: str
    ) -> List[CollectionItem]:
        """根据文档类型生成收集项"""
        items = []
        
        # 基础信息收集项
        base_items = [
            CollectionItem(
                id="project_name",
                field="project_name",
                label="项目名称",
                type=CollectionType.TEXT_INPUT,
                hint="请输入完整项目名称",
            ),
            CollectionItem(
                id="location",
                field="location",
                label="项目地点",
                type=CollectionType.MAP_SELECTION,  # 地图选点
                hint="点击地图选择位置，或输入地址",
            ),
            CollectionItem(
                id="industry",
                field="industry",
                label="行业类型",
                type=CollectionType.SELECT_CHOICE,
                options=self._get_industry_options(industry),
            ),
            CollectionItem(
                id="scale",
                field="scale",
                label="项目规模",
                type=CollectionType.SELECT_CHOICE,
                options=["小型", "中型", "大型", "超大型"],
            ),
        ]
        items.extend(base_items)
        
        # 根据文档类型添加特定项
        if "eia" in doc_type.lower() or "环境" in doc_type:
            items.extend([
                CollectionItem(
                    id="main_products",
                    field="main_products",
                    label="主要产品",
                    type=CollectionType.TEXT_INPUT,
                    hint="如：聚氯乙烯、盐酸等",
                ),
                CollectionItem(
                    id="raw_materials",
                    field="raw_materials",
                    label="主要原料",
                    type=CollectionType.MULTI_CHOICE,
                    options=["煤炭", "石油", "天然气", "矿石", "农产品", "其他"],
                ),
                CollectionItem(
                    id="pollutants",
                    field="pollutants",
                    label="主要污染物",
                    type=CollectionType.MULTI_CHOICE,
                    options=["废气", "废水", "固废", "噪声", "辐射"],
                ),
                CollectionItem(
                    id="sensitive_targets",
                    field="sensitive_targets",
                    label="周边敏感目标",
                    type=CollectionType.TEXT_INPUT,
                    hint="如：居民区、学校、医院等",
                ),
                CollectionItem(
                    id="layout_file",
                    field="layout_file",
                    label="平面布局图",
                    type=CollectionType.IMAGE_UPLOAD,
                    hint="上传项目平面布局图或示意图",
                    required=False,
                ),
                CollectionItem(
                    id="drainage_direction",
                    field="drainage_direction",
                    label="排水去向",
                    type=CollectionType.SELECT_CHOICE,
                    options=["市政管网", "河流", "湖泊", "海域", "回用"],
                ),
            ])
            
        elif "feasibility" in doc_type.lower() or "可行" in doc_type:
            items.extend([
                CollectionItem(
                    id="investment",
                    field="investment",
                    label="投资金额（万元）",
                    type=CollectionType.NUMBER_INPUT,
                    hint="请输入数字",
                    unit="万元",
                    min_value=0,
                    max_value=1000000,
                ),
                CollectionItem(
                    id="construction_period",
                    field="construction_period",
                    label="建设周期",
                    type=CollectionType.NUMBER_INPUT,
                    hint="预计建设时间",
                    unit="个月",
                    min_value=1,
                    max_value=120,
                ),
                CollectionItem(
                    id="annual_revenue",
                    field="annual_revenue",
                    label="预计年营业收入",
                    type=CollectionType.NUMBER_INPUT,
                    hint="预计年度营业收入",
                    unit="万元",
                    min_value=0,
                    required=False,
                ),
                CollectionItem(
                    id="employment",
                    field="employment",
                    label="新增就业人数",
                    type=CollectionType.NUMBER_INPUT,
                    hint="预计新增就业",
                    unit="人",
                    min_value=0,
                    required=False,
                ),
                CollectionItem(
                    id="market_analysis_file",
                    field="market_analysis_file",
                    label="市场分析资料",
                    type=CollectionType.FILE_UPLOAD,
                    hint="上传市场调研报告或数据",
                    required=False,
                ),
            ])
            
        elif "safety" in doc_type.lower() or "安全" in doc_type:
            items.extend([
                CollectionItem(
                    id="major_hazards",
                    field="major_hazards",
                    label="重大危险源",
                    type=CollectionType.MULTI_CHOICE,
                    options=["易燃液体", "易燃气体", "有毒物质", "爆炸品", "高温高压", "其他"],
                ),
                CollectionItem(
                    id="hazard_chemicals",
                    field="hazard_chemicals",
                    label="危险化学品清单",
                    type=CollectionType.FILE_UPLOAD,
                    hint="上传MSDS或化学品清单",
                ),
                CollectionItem(
                    id="existing_safety_measures",
                    field="existing_safety_measures",
                    label="现有安全措施",
                    type=CollectionType.MULTI_CHOICE,
                    options=["监控系统", "报警系统", "防护设施", "应急预案", "安全培训"],
                ),
                CollectionItem(
                    id="accident_history",
                    field="accident_history",
                    label="近5年事故情况",
                    type=CollectionType.SELECT_CHOICE,
                    options=["无事故", "轻微事故已整改", "一般事故已整改", "较大事故"],
                ),
                CollectionItem(
                    id="site_layout_file",
                    field="site_layout_file",
                    label="厂区平面布置图",
                    type=CollectionType.IMAGE_UPLOAD,
                    hint="上传厂区平面布置图，标注重大危险源位置",
                ),
            ])
        
        # 添加日期收集项
        items.append(CollectionItem(
            id="expected_start_date",
            field="expected_start_date",
            label="预计开工时间",
            type=CollectionType.DATE_PICKER,
            required=False,
        ))
        
        return items
    
    def _get_industry_options(self, current_industry: Optional[str] = None) -> List[str]:
        """获取行业选项"""
        industries = [
            "化工", "制药", "电子", "造纸", "纺织", "食品",
            "钢铁", "有色金属", "建材", "机械", "汽车", "轻工",
            "农业", "畜牧", "矿产", "能源", "交通", "市政",
            "房地产", "旅游", "教育", "医疗", "其他"
        ]
        
        # 如果有当前行业，排在第一位
        if current_industry and current_industry in industries:
            industries.remove(current_industry)
            industries.insert(0, current_industry)
            
        return industries
    
    def _auto_collect(self, session: CollectionSession, requirement: str) -> CollectionSession:
        """自动采集可获取的数据"""
        if not self.data_collector:
            return session
            
        try:
            # 1. 从需求文本中提取
            extracted = self._extract_from_requirement(requirement)
            
            for item in session.items:
                if item.field in extracted and extracted[item.field]:
                    result = CollectionResult(
                        item_id=item.id,
                        field=item.field,
                        value=extracted[item.field],
                        source="ai_extraction",
                        confidence=0.8,
                    )
                    session.results[item.id] = result
                    session.completed.append(item.id)
                    session.auto_collected_count += 1
                    
            # 2. 地理位置自动采集
            if "location" not in session.completed:
                location_result = self._try_auto_location(requirement)
                if location_result:
                    session.results["location"] = location_result
                    session.completed.append("location")
                    session.auto_collected_count += 1
                    
        except Exception as e:
            logger.debug(f"自动采集失败: {e}")
            
        # 更新待收集项
        session.pending = [i.id for i in session.items if i.id not in session.completed]
        return session
    
    def _extract_from_requirement(self, requirement: str) -> Dict[str, Any]:
        """从需求中提取信息"""
        extracted = {}
        import re
        
        # 提取投资金额
        amounts = re.findall(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:万|亿)?\s*元", requirement)
        if amounts:
            extracted["investment"] = amounts[0]
            
        # 提取地点
        locations = re.findall(r"在([^在\s]{2,10}(?:省|市|县|区))", requirement)
        if locations:
            extracted["location"] = locations[0]
            
        # 提取行业
        industries = ["化工", "制药", "电子", "造纸", "钢铁", "煤矿", "光伏", "风电"]
        for ind in industries:
            if ind in requirement:
                extracted["industry"] = ind
                break
                
        return extracted
    
    def _try_auto_location(self, requirement: str) -> Optional[CollectionResult]:
        """尝试自动获取位置"""
        if not self.data_collector:
            return None
            
        try:
            # 从需求中提取地址关键词
            import re
            locations = re.findall(r"在?([^\s，。、；：！]{2,10}(?:省|市|县|区|镇))", requirement)
            
            if locations:
                location = locations[0]
                
                # 调用数据采集器获取坐标
                coords = self.data_collector.get_coordinates(location)
                
                if coords:
                    return CollectionResult(
                        item_id="location",
                        field="location",
                        value={
                            "address": location,
                            "latitude": coords.get("lat"),
                            "longitude": coords.get("lon"),
                        },
                        source="auto_geocoding",
                        confidence=0.9,
                        metadata={"raw_address": location}
                    )
                    
        except Exception as e:
            logger.debug(f"自动位置获取失败: {e}")
            
        return None
    
    def get_next_item(self, session: CollectionSession) -> Optional[CollectionItem]:
        """
        获取下一个需要收集的项
        
        Returns:
            CollectionItem 或 None（已全部完成）
        """
        pending_items = session.get_pending_items()
        
        if not pending_items:
            return None
            
        # 优先返回有AI建议的项
        for item in pending_items:
            if item.ai_suggest:
                return item
                
        # 否则按顺序返回第一个
        return pending_items[0]
    
    def get_ui_options(self, item: CollectionItem) -> Dict[str, Any]:
        """
        获取UI渲染选项
        
        Args:
            item: 收集项
        
        Returns:
            Dict: UI配置选项
        """
        options = {
            "id": item.id,
            "field": item.field,
            "label": item.label,
            "type": item.type.value,
            "hint": item.hint,
            "required": item.required,
        }
        
        if item.type == CollectionType.SELECT_CHOICE:
            options["options"] = item.options or []
            options["multiple"] = False
            
        elif item.type == CollectionType.MULTI_CHOICE:
            options["options"] = item.options or []
            options["multiple"] = True
            
        elif item.type == CollectionType.NUMBER_INPUT:
            options["min"] = item.min_value
            options["max"] = item.max_value
            options["unit"] = item.unit
            options["step"] = 1 if item.unit in ["个", "人"] else 0.1
            
        elif item.type == CollectionType.RANGE_SLIDER:
            options["min"] = item.min_value or 0
            options["max"] = item.max_value or 100
            options["unit"] = item.unit
            options["default"] = item.default_value or item.min_value
            
        elif item.type == CollectionType.MAP_SELECTION:
            # 地图选点配置
            options["enable_drawing"] = True
            options["default_center"] = [30.52, 114.31]  # 默认武汉
            options["default_zoom"] = 10
            
        elif item.type == CollectionType.DATE_PICKER:
            options["format"] = "YYYY-MM-DD"
            
        elif item.type in [CollectionType.FILE_UPLOAD, CollectionType.IMAGE_UPLOAD]:
            options["accept"] = ".pdf,.doc,.docx,.jpg,.png" if item.type == CollectionType.FILE_UPLOAD else ".jpg,.png,.pdf"
            options["max_size"] = 10  # MB
            
        return options
    
    def submit(
        self,
        session: CollectionSession,
        item_id: str,
        value: Any,
        source: str = "user_input"
    ) -> CollectionSession:
        """
        提交收集结果
        
        Args:
            session: 收集会话
            item_id: 收集项ID
            value: 收集值
            source: 来源
        
        Returns:
            CollectionSession: 更新后的会话
        """
        # 查找项
        item = next((i for i in session.items if i.id == item_id), None)
        if not item:
            logger.warning(f"未找到收集项: {item_id}")
            return session
            
        # 验证值
        if item.required and not value:
            logger.warning(f"必填项不能为空: {item_id}")
            return session
            
        # 保存结果
        result = CollectionResult(
            item_id=item_id,
            field=item.field,
            value=value,
            source=source,
            confidence=1.0 if source == "user_input" else 0.8,
        )
        session.results[item_id] = result
        
        # 更新完成状态
        if item_id not in session.completed:
            session.completed.append(item_id)
            
        if item_id in session.pending:
            session.pending.remove(item_id)
            
        if source == "user_input":
            session.user_input_count += 1
        else:
            session.auto_collected_count += 1
            
        # 检查依赖项，触发后续收集
        session = self._check_dependencies(session, item_id, value)
        
        # 更新阶段
        session.stage = self._update_stage(session)
        
        return session
    
    def submit_file(
        self,
        session: CollectionSession,
        item_id: str,
        file_path: str
    ) -> CollectionSession:
        """
        提交文件（自动分析）
        
        Args:
            session: 收集会话
            item_id: 收集项ID
            file_path: 文件路径
        
        Returns:
            CollectionSession: 更新后的会话
        """
        if not self.doc_analyzer:
            return session
            
        try:
            # 分析文件
            import asyncio
            doc_result = asyncio.get_event_loop().run_until_complete(
                self.doc_analyzer.analyze(file_path)
            )
            
            # 提取相关信息
            extracted = {
                "file_path": file_path,
                "file_name": doc_result.title,
                "entities": doc_result.entities,
                "content_summary": doc_result.cleaned_content[:500] if doc_result.cleaned_content else "",
            }
            
            # 特殊处理：根据文件类型更新相关字段
            if "layout" in item_id or "平面" in item_id:
                # 平面图文件，分析后可以提取位置信息
                session = self.submit(session, item_id, extracted, source="file_analysis")
                
                # 尝试提取布局中的文字信息
                if doc_result.entities.get("locations"):
                    session = self.submit(
                        session, "location",
                        doc_result.entities["locations"][0],
                        source="file_extraction"
                    )
                    
            else:
                session = self.submit(session, item_id, extracted, source="file_analysis")
                
        except Exception as e:
            logger.error(f"文件分析失败: {file_path}, {e}")
            
        return session
    
    def submit_location(
        self,
        session: CollectionSession,
        location_data: Dict[str, Any]
    ) -> CollectionSession:
        """
        提交地图位置
        
        Args:
            session: 收集会话
            location_data: 位置数据，包含：
                - address: 地址
                - latitude: 纬度
                - longitude: 经度
                - polygon: 区域多边形（可选）
        
        Returns:
            CollectionSession: 更新后的会话
        """
        return self.submit(session, "location", location_data, source="map_selection")
    
    def _check_dependencies(
        self,
        session: CollectionSession,
        completed_item_id: str,
        value: Any
    ) -> CollectionSession:
        """检查依赖项"""
        # 当行业变化时，更新相关选项
        if completed_item_id == "industry" and value:
            for item in session.items:
                if item.field == "pollutants" and item.options:
                    # 根据行业更新污染物选项
                    item.options = self._get_pollutants_options(value)
                    
        return session
    
    def _get_pollutants_options(self, industry: str) -> List[str]:
        """根据行业获取污染物选项"""
        base_pollutants = ["废气", "废水", "固废", "噪声"]
        
        industry_pollutants = {
            "化工": ["VOC", "硫化氢", "氨气", "氯气"],
            "制药": ["VOC", "有机溶剂", "发酵废气"],
            "造纸": ["COD", "色度", "硫化物"],
            "钢铁": ["粉尘", "SO2", "NOx"],
            "煤矿": ["甲烷", "粉尘", "矸石"],
        }
        
        specific = industry_pollutants.get(industry, [])
        return base_pollutants + specific
    
    def _update_stage(self, session: CollectionSession) -> str:
        """更新会话阶段"""
        completed_ids = set(session.completed)
        
        # 定义阶段
        basic_fields = {"project_name", "location", "industry"}
        scale_fields = {"scale", "investment"}
        technical_fields = {"main_products", "raw_materials", "pollutants"}
        file_fields = {"layout_file", "hazard_chemicals", "site_layout_file"}
        
        if completed_ids.issuperset(basic_fields):
            if completed_ids.issuperset(scale_fields):
                if completed_ids.issuperset(technical_fields):
                    if completed_ids.issuperset(file_fields):
                        return "completed"
                    return "document_upload"
                return "technical_details"
            return "scale_definition"
        return "basic_info"
    
    def get_stage_prompt(self, session: CollectionSession) -> str:
        """获取当前阶段提示"""
        prompts = {
            "initial": "正在分析需求...",
            "basic_info": f"请完善基本信息（{len([i for i in session.items if i.id not in session.completed and i.field in ['project_name', 'location', 'industry']])}项待填）",
            "scale_definition": "请确定项目规模和投资信息",
            "technical_details": "请提供技术工艺和污染物信息",
            "document_upload": "请上传相关图纸和资料",
            "completed": "资料收集完成！",
        }
        return prompts.get(session.stage, "")
    
    def get_ai_suggestions(self, session: CollectionSession) -> List[Dict[str, Any]]:
        """获取AI建议"""
        suggestions = []
        
        # 从已收集的数据推断
        results = session.results
        
        # 投资建议
        if "investment" in results and "industry" in results:
            suggestions.append({
                "type": "info",
                "field": "investment",
                "message": f"{results['industry'].value}行业同类项目平均投资强度约为 XX万元/公顷"
            })
            
        # 污染物建议
        if "industry" in results and "pollutants" not in results:
            industry = results["industry"].value
            typical = self._get_pollutants_options(industry)
            suggestions.append({
                "type": "recommendation",
                "field": "pollutants",
                "message": f"根据{industry}行业特点，建议关注：{', '.join(typical[:3])}",
                "suggested_values": typical[:3],
            })
            
        return suggestions
    
    def complete_session(self, session: CollectionSession) -> Dict[str, Any]:
        """
        完成收集会话
        
        Returns:
            Dict: 收集结果
        """
        # 合并所有结果
        final_data = {}
        
        for result in session.results.values():
            if result.field not in final_data or not final_data[result.field]:
                final_data[result.field] = result.value
                
        # 检查未完成的必填项
        missing_required = [
            i.label for i in session.items
            if i.required and i.id not in session.completed
        ]
        
        return {
            "session_id": session.id,
            "doc_type": session.doc_type,
            "data": final_data,
            "completion_rate": session.get_completion_rate(),
            "auto_collected": session.auto_collected_count,
            "user_inputs": session.user_input_count,
            "missing_required": missing_required,
            "can_proceed": len(missing_required) == 0,
            "summary": self._generate_summary(session),
        }
    
    def _generate_summary(self, session: CollectionSession) -> str:
        """生成收集摘要"""
        lines = []
        
        lines.append(f"📊 资料收集完成度: {session.get_completion_rate()*100:.0f}%")
        lines.append(f"   - 自动采集: {session.auto_collected_count}项")
        lines.append(f"   - 手动输入: {session.user_input_count}项")
        
        if session.results:
            lines.append("\n📋 已收集信息:")
            for result in session.results.values():
                value = result.value
                if isinstance(value, dict):
                    value = f"{value.get('address', value.get('file_name', '...'))}"
                elif isinstance(value, list):
                    value = ", ".join(str(v) for v in value[:3])
                lines.append(f"   - {result.field}: {value}")
                
        return "\n".join(lines)
    
    def cancel_session(self, session_id: str) -> bool:
        """取消会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


# 全局实例
_collector: Optional[InteractiveCollector] = None


def get_interactive_collector() -> InteractiveCollector:
    """获取全局交互式收集器"""
    global _collector
    if _collector is None:
        _collector = InteractiveCollector()
    return _collector
