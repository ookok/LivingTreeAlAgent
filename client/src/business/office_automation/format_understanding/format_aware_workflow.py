"""
🔄 格式感知的 AI 工作流 - Format-Aware AI Workflow

三大核心能力：

1. 格式保持的内容生成
   输入: 目标格式约束
   ↓
   格式分析: 分析可用空间、样式要求
   ↓
   内容规划: 在格式约束下规划内容
   ↓
   格式同步生成: 内容和格式同步生成
   ↓
   格式验证: 检查内容与格式的兼容性
   ↓
   输出: 格式完美匹配的内容

2. 智能格式迁移
   源文档 + 源格式 → 格式分析 → 目标模板 → 格式映射 → 格式应用 → 输出

3. 格式一致性检查
   文档集合 → 格式提取 → 格式聚类 → 异常检测 → 智能修复 → 输出
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable, Tuple

from business.office_automation.format_understanding.format_parser import FormatParser, FormatInfo
from business.office_automation.format_understanding.format_graph import FormatGraph, FormatNode, NodeType
from business.office_automation.format_understanding.format_semantic import FormatSemanticModel, FormatIntent
from business.office_automation.format_understanding.format_evaluator import FormatEvaluator, QualityMetrics
from business.office_automation.format_understanding.format_knowledge import FormatKnowledgeBase

logger = logging.getLogger(__name__)


class WorkflowType(Enum):
    """工作流类型"""
    FORMAT_AWARE_CREATE = "format_aware_create"
    FORMAT_PRESERVING_EDIT = "format_preserving_edit"
    SMART_FORMAT_MIGRATION = "smart_format_migration"
    FORMAT_CONSISTENCY_CHECK = "format_consistency_check"


@dataclass
class FormatConstraint:
    """格式约束"""
    # 空间约束
    max_length: int = 0             # 最大字符数
    max_lines: int = 0             # 最大行数
    available_width: float = 0.0   # 可用宽度 (pt)

    # 样式约束
    required_style: str = ""       # 要求的样式名
    font_name: str = ""            # 字体
    font_size: float = 0.0         # 字号
    line_spacing: float = 0.0     # 行距
    alignment: str = ""            # 对齐

    # 内容约束
    must_include: List[str] = field(default_factory=list)  # 必须包含的内容
    must_not_include: List[str] = field(default_factory=list)  # 禁止包含的内容

    # 语义约束
    semantic_role: str = ""       # 语义角色
    importance_level: int = 0     # 重要性等级


@dataclass
class ContentPlan:
    """内容规划"""
    # 结构规划
    sections: List[Dict] = field(default_factory=list)  # 各部分内容大纲
    total_length: int = 0          # 规划总长度
    estimated_lines: int = 0      # 估计行数

    # 格式适配
    format_constraints: List[FormatConstraint] = field(default_factory=list)
    style_to_apply: Dict = field(default_factory=dict)

    # 生成策略
    generation_strategy: str = ""  # "concise"/"balanced"/"detailed"
    preserve_list_format: bool = True
    preserve_heading_hierarchy: bool = True


class FormatAwareWorkflow:
    """
    格式感知的 AI 工作流

    在内容生成过程中全程考虑格式约束，确保输出符合格式要求
    """

    def __init__(self, knowledge_base: FormatKnowledgeBase = None):
        self.parser = FormatParser()
        self.semantic_model = FormatSemanticModel()
        self.evaluator = FormatEvaluator()
        self.knowledge = knowledge_base or FormatKnowledgeBase()

    # ===== 1. 格式保持的内容生成 =====

    async def format_aware_create(
        self,
        requirement: str,
        format_constraints: FormatConstraint,
        model_router,
        progress_callback: Callable = None,
    ) -> Dict[str, Any]:
        """
        格式保持的内容生成

        Args:
            requirement: 内容需求描述
            format_constraints: 格式约束
            model_router: 模型路由器
            progress_callback: 进度回调

        Returns:
            生成的内容 + 格式信息
        """
        result = {
            "content": "",
            "format": {},
            "quality_score": 0.0,
            "issues": [],
        }

        try:
            if progress_callback:
                progress_callback(10, "分析格式约束...")

            # 1. 分析格式约束
            constraint_analysis = self._analyze_constraints(format_constraints)
            result["constraint_analysis"] = constraint_analysis

            if progress_callback:
                progress_callback(30, "规划内容结构...")

            # 2. 内容规划 - 在格式约束下规划
            content_plan = self._plan_content(requirement, format_constraints)
            result["content_plan"] = content_plan

            if progress_callback:
                progress_callback(50, "生成内容...")

            # 3. 格式感知的内容生成
            content = await self._generate_format_aware_content(
                requirement, content_plan, format_constraints, model_router
            )
            result["content"] = content

            if progress_callback:
                progress_callback(70, "验证格式兼容性...")

            # 4. 格式验证
            validation = self._validate_format_compatibility(content, format_constraints)
            result["validation"] = validation

            if progress_callback:
                progress_callback(90, "计算质量分数...")

            # 5. 质量评估
            quality_score = self._calculate_quality_score(content, format_constraints, validation)
            result["quality_score"] = quality_score

            if progress_callback:
                progress_callback(100, "完成")

        except Exception as e:
            logger.error(f"格式感知生成失败: {e}")
            result["issues"].append(str(e))

        return result

    def _analyze_constraints(self, constraints: FormatConstraint) -> Dict:
        """分析格式约束"""
        analysis = {
            "space_available": constraints.max_length > 0,
            "style_required": bool(constraints.required_style),
            "semantic_constraints": bool(constraints.semantic_role),
            "adjustable_fields": [],
            "fixed_fields": [],
        }

        # 判断哪些字段可调整
        if constraints.max_length == 0:
            analysis["adjustable_fields"].append("length")
        else:
            analysis["fixed_fields"].append("length")

        if constraints.font_size == 0:
            analysis["adjustable_fields"].append("font_size")
        else:
            analysis["fixed_fields"].append("font_size")

        return analysis

    def _plan_content(self, requirement: str, constraints: FormatConstraint) -> ContentPlan:
        """规划内容以满足格式约束"""
        plan = ContentPlan()

        # 确定生成策略
        if constraints.max_length > 0 and constraints.max_length < 200:
            plan.generation_strategy = "concise"
        elif constraints.max_length > 500:
            plan.generation_strategy = "detailed"
        else:
            plan.generation_strategy = "balanced"

        # 估计可用空间
        if constraints.max_length > 0:
            plan.total_length = constraints.max_length
            plan.estimated_lines = constraints.max_length // 50  # 粗略估计

        # 样式映射
        if constraints.required_style:
            plan.style_to_apply = {
                "style_name": constraints.required_style,
                "font": constraints.font_name,
                "size": constraints.font_size,
                "spacing": constraints.line_spacing,
            }

        return plan

    async def _generate_format_aware_content(
        self,
        requirement: str,
        plan: ContentPlan,
        constraints: FormatConstraint,
        model_router,
    ) -> str:
        """生成格式感知的内容"""
        # 构建格式约束的提示
        constraint_prompt = self._build_constraint_prompt(plan, constraints)

        # 调用模型生成
        planner = model_router.route(ModelCapability.CONTENT_GENERATION)

        prompt = f"""{requirement}

{constraint_prompt}

请生成符合上述格式约束的内容。"""

        content = await model_router.call_model(
            planner,
            prompt,
            system_prompt="你是一个专业的内容撰写专家，擅长在严格格式约束下生成内容。"
        )

        return content

    def _build_constraint_prompt(self, plan: ContentPlan, constraints: FormatConstraint) -> str:
        """构建格式约束的提示"""
        lines = ["【格式约束】"]

        if constraints.max_length > 0:
            lines.append(f"- 内容长度: 不超过 {constraints.max_length} 字符")
            lines.append(f"- 估计行数: {plan.estimated_lines} 行")

        if constraints.font_name:
            lines.append(f"- 字体: {constraints.font_name}")

        if constraints.font_size > 0:
            lines.append(f"- 字号: {constraints.font_size}pt")

        if constraints.alignment:
            align_map = {"center": "居中", "left": "左对齐", "right": "右对齐", "justify": "两端对齐"}
            lines.append(f"- 对齐: {align_map.get(constraints.alignment, constraints.alignment)}")

        if constraints.semantic_role:
            lines.append(f"- 语义角色: {constraints.semantic_role}")

        if constraints.must_include:
            lines.append(f"- 必须包含: {', '.join(constraints.must_include)}")

        return "\n".join(lines)

    def _validate_format_compatibility(self, content: str,
                                       constraints: FormatConstraint) -> Dict:
        """验证内容与格式的兼容性"""
        validation = {
            "compatible": True,
            "issues": [],
            "warnings": [],
        }

        # 长度检查
        if constraints.max_length > 0:
            if len(content) > constraints.max_length:
                validation["compatible"] = False
                validation["issues"].append({
                    "type": "length_overflow",
                    "message": f"内容长度 ({len(content)}) 超出限制 ({constraints.max_length})",
                    "severity": "error",
                })
            elif len(content) > constraints.max_length * 0.9:
                validation["warnings"].append({
                    "type": "length_warning",
                    "message": f"内容长度接近限制 (90%)",
                    "severity": "warning",
                })

        # 必含内容检查
        for must_have in constraints.must_include:
            if must_have not in content:
                validation["compatible"] = False
                validation["issues"].append({
                    "type": "missing_content",
                    "message": f"缺少必需内容: {must_have}",
                    "severity": "error",
                })

        # 禁止内容检查
        for must_not_have in constraints.must_not_include:
            if must_not_have in content:
                validation["compatible"] = False
                validation["issues"].append({
                    "type": "forbidden_content",
                    "message": f"包含禁止内容: {must_not_have}",
                    "severity": "error",
                })

        return validation

    def _calculate_quality_score(self, content: str, constraints: FormatConstraint,
                                  validation: Dict) -> float:
        """计算质量分数"""
        score = 100.0

        # 长度分数
        if constraints.max_length > 0:
            length_ratio = len(content) / constraints.max_length
            if length_ratio > 1.0:
                score -= 30
            elif length_ratio > 0.9:
                score -= 10
            elif length_ratio < 0.5:
                score -= 15

        # 验证分数
        if not validation["compatible"]:
            score -= len(validation["issues"]) * 20

        # 警告分数
        score -= len(validation["warnings"]) * 5

        return max(0.0, min(100.0, score))

    # ===== 2. 智能格式迁移 =====

    async def smart_format_migration(
        self,
        source_file: str,
        target_template: str,
        model_router,
        progress_callback: Callable = None,
    ) -> Dict[str, Any]:
        """
        智能格式迁移

        将内容从一个文档迁移到另一个模板，同时智能映射格式
        """
        result = {
            "success": False,
            "migrated_content": "",
            "format_mapping": {},
            "issues": [],
        }

        try:
            if progress_callback:
                progress_callback(20, "解析源文档格式...")

            # 1. 解析源文档
            source_format = self.parser.parse(source_file)
            result["source_format"] = source_format.to_dict()

            if progress_callback:
                progress_callback(40, "解析目标模板格式...")

            # 2. 解析目标模板
            target_format = self.parser.parse(target_template)
            result["target_format"] = target_format.to_dict()

            if progress_callback:
                progress_callback(60, "智能映射格式...")

            # 3. 格式映射
            mapping = self._create_format_mapping(source_format, target_format)
            result["format_mapping"] = mapping

            if progress_callback:
                progress_callback(80, "应用格式...")

            # 4. 内容迁移
            migrated_content = self._apply_format_mapping(
                source_format, target_format, mapping
            )
            result["migrated_content"] = migrated_content
            result["success"] = True

            if progress_callback:
                progress_callback(100, "完成")

        except Exception as e:
            logger.error(f"格式迁移失败: {e}")
            result["issues"].append(str(e))

        return result

    def _create_format_mapping(self, source: FormatInfo, target: FormatInfo) -> Dict:
        """创建格式映射规则"""
        mapping = {
            "direct_mappings": {},     # 直接对应
            "semantic_mappings": {},   # 语义对应
            "adaptive_mappings": {},   # 自适应调整
            "unmapped": [],            # 无法映射
        }

        # 直接映射 (相同的样式)
        for style_id, style_info in source.styles.items():
            if style_id in target.styles:
                mapping["direct_mappings"][style_id] = style_id

        # 语义映射 (相似语义的样式)
        for src_id, src_style in source.styles.items():
            src_name = src_style.get("name", "").lower()
            src_type = self._classify_style_type(src_name)

            for tgt_id, tgt_style in target.styles.items():
                tgt_name = tgt_style.get("name", "").lower()
                tgt_type = self._classify_style_type(tgt_name)

                if src_type == tgt_type and src_type != "unknown":
                    mapping["semantic_mappings"][src_id] = tgt_id

        return mapping

    def _classify_style_type(self, style_name: str) -> str:
        """分类样式类型"""
        name = style_name.lower()

        if any(kw in name for kw in ["heading", "标题", "h1", "h2", "h3"]):
            return "heading"
        elif any(kw in name for kw in ["body", "正文", "paragraph"]):
            return "body"
        elif any(kw in name for kw in ["title", "标题"]):
            return "title"
        elif any(kw in name for kw in ["caption", "说明", "note"]):
            return "caption"
        elif any(kw in name for kw in ["code", "代码"]):
            return "code"
        else:
            return "unknown"

    def _apply_format_mapping(self, source: FormatInfo, target: FormatInfo,
                              mapping: Dict) -> str:
        """应用格式映射"""
        migrated = []

        for element in source.elements:
            # 获取映射后的样式
            style_id = element.structural.style_id
            mapped_style = mapping["semantic_mappings"].get(style_id, style_id)

            # 构建迁移后的元素
            migrated_element = {
                "text": element.text_content,
                "mapped_style": mapped_style,
                "visual": element.visual.to_dict(),
            }
            migrated.append(migrated_element)

        return str(migrated)  # 简化返回

    # ===== 3. 格式一致性检查 =====

    def format_consistency_check(
        self,
        documents: List[str],
        standard_id: str = None,
    ) -> Dict[str, Any]:
        """
        批量检查文档格式一致性
        """
        result = {
            "total_documents": len(documents),
            "analyzed": [],
            "inconsistencies": [],
            "recommendations": [],
        }

        # 解析所有文档
        formats = []
        for doc_path in documents:
            try:
                fmt = self.parser.parse(doc_path)
                formats.append(fmt)
                result["analyzed"].append({
                    "path": doc_path,
                    "styles": len(fmt.styles),
                    "elements": len(fmt.elements),
                })
            except Exception as e:
                result["anconsistencies"].append({
                    "document": doc_path,
                    "error": str(e),
                })

        if len(formats) < 2:
            return result

        # 检测不一致
        inconsistencies = self._detect_inconsistencies(formats)
        result["inconsistencies"] = inconsistencies

        # 生成建议
        recommendations = self._generate_consistency_recommendations(formats, inconsistencies)
        result["recommendations"] = recommendations

        return result

    def _detect_inconsistencies(self, formats: List[FormatInfo]) -> List[Dict]:
        """检测格式不一致"""
        inconsistencies = []

        # 字体一致性检查
        fonts = [f.primary_font for f in formats if f.primary_font]
        if fonts and len(set(fonts)) > 1:
            inconsistencies.append({
                "type": "font_inconsistency",
                "message": f"文档使用不同主字体: {set(fonts)}",
                "severity": "warning",
            })

        # 样式数量检查
        style_counts = [len(f.styles) for f in formats]
        if style_counts and max(style_counts) / max(min(style_counts), 1) > 2:
            inconsistencies.append({
                "type": "style_count_inconsistency",
                "message": f"样式数量差异过大: {style_counts}",
                "severity": "info",
            })

        return inconsistencies

    def _generate_consistency_recommendations(self, formats: List[FormatInfo],
                                              inconsistencies: List[Dict]) -> List[Dict]:
        """生成一致性改进建议"""
        recommendations = []

        if any(i["type"] == "font_inconsistency" for i in inconsistencies):
            # 建议统一字体
            most_common_font = max(set(f.primary_font for f in formats if f.primary_font),
                                  default="Microsoft YaHei")
            recommendations.append({
                "action": "standardize_font",
                "suggestion": f"建议统一使用字体: {most_common_font}",
                "priority": "high",
            })

        return recommendations


# ===== 导出到主模块的便捷函数 =====

def create_format_aware_workflow() -> FormatAwareWorkflow:
    """创建格式感知工作流"""
    return FormatAwareWorkflow()


async def generate_with_format_constraint(
    requirement: str,
    constraints: Dict,
    model_router,
) -> Dict[str, Any]:
    """便捷函数: 带格式约束的内容生成"""
    from dataclasses import dataclass, field

    @dataclass
    class SimpleConstraint:
        max_length: int = 0
        font_name: str = ""
        font_size: float = 0.0
        alignment: str = ""
        semantic_role: str = ""
        must_include: List[str] = field(default_factory=list)
        must_not_include: List[str] = field(default_factory=list)

    constraint = SimpleConstraint(**constraints) if constraints else SimpleConstraint()
    workflow = FormatAwareWorkflow()

    return await workflow.format_aware_create(
        requirement=requirement,
        format_constraints=constraint,
        model_router=model_router,
    )
