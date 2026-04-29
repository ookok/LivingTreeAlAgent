"""
🏢 Office 管理器 - 智能中枢

统一入口，协调所有子模块：
- 意图解析 → 模型路由 → 工作流执行 → 引擎渲染 → 质量检查

对外暴露简洁 API:
- create_document(): 创建文档
- fill_document(): 填充文档
- format_document(): 格式化文档
- analyze_document(): 分析文档
"""

import os
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Any
from datetime import datetime

from core.office_automation.document_context import (
    DocumentContext, DocumentIntent, IntentParser, DocumentType, OutputFormat
)
from core.office_automation.design_system import DesignSystem, DocumentTheme
from core.office_automation.template_router import TemplateRouter, TemplateMatch, CoverStyle
from core.office_automation.model_router import ModelRouter, ModelCapability
from core.office_automation.quality_checker import QualityChecker, QualityReport
from core.office_automation.workflows import (
    CreateWorkflow, FillEditWorkflow, FormatApplyWorkflow,
    WorkflowType, WorkflowResult, WorkflowStatus,
)
from core.office_automation.engines import EngineFactory, EngineType

# 格式理解引擎
from core.office_automation.format_understanding.format_parser import FormatParser, FormatInfo
from core.office_automation.format_understanding.format_graph import FormatGraph
from core.office_automation.format_understanding.format_semantic import FormatSemanticModel
from core.office_automation.format_understanding.format_evaluator import FormatEvaluator
from core.office_automation.format_understanding.format_knowledge import FormatKnowledgeBase
from core.office_automation.format_understanding.format_aware_workflow import FormatAwareWorkflow

logger = logging.getLogger(__name__)


@dataclass
class OfficeTask:
    """办公任务"""
    task_id: str
    workflow_type: WorkflowType
    context: DocumentContext
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: Optional[WorkflowResult] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "workflow_type": self.workflow_type.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "result": self.result.to_dict() if self.result else None,
        }


class OfficeManager:
    """
    Office 自动化管理器

    智能中枢，协调:
    - IntentParser: 意图解析
    - ModelRouter: 模型路由
    - TemplateRouter: 模板路由
    - DesignSystem: 设计系统
    - QualityChecker: 质量检查
    - EngineFactory: 引擎工厂
    - Workflows: 三大工作流
    """

    def __init__(self, config: dict = None):
        self.config = config or {}

        # 初始化子模块
        self.intent_parser = IntentParser()
        self.model_router = ModelRouter()
        self.template_router = TemplateRouter(
            custom_templates_dir=self.config.get("templates_dir")
        )
        self.design_system = DesignSystem(
            config_dir=self.config.get("config_dir")
        )
        self.quality_checker = QualityChecker(
            brand_rules=self.config.get("brand_rules")
        )

        # 工作流
        self.create_workflow = CreateWorkflow(
            self.model_router, self.template_router, self.design_system
        )
        self.fill_edit_workflow = FillEditWorkflow(self.model_router)
        self.format_apply_workflow = FormatApplyWorkflow(
            self.model_router, self.design_system
        )

        # 🎨 格式理解引擎
        self.format_parser = FormatParser()
        self.format_semantic = FormatSemanticModel()
        self.format_evaluator = FormatEvaluator(
            brand_rules=self.config.get("brand_rules")
        )
        self.format_knowledge = FormatKnowledgeBase(
            storage_dir=self.config.get("knowledge_dir")
        )
        self.format_aware_workflow = FormatAwareWorkflow(
            knowledge_base=self.format_knowledge
        )

        # 任务历史
        self.tasks: Dict[str, OfficeTask] = {}
        self._task_counter = 0

        logger.info("Office 管理器初始化完成 (含格式智能系统)")

    # ===== 主要 API =====

    async def create_document(self, request: str, custom_data: dict = None,
                              progress_callback: Callable = None) -> dict:
        """
        从零创建专业文档

        Args:
            request: 自然语言需求描述
            custom_data: 自定义数据 (覆盖自动推断)
            progress_callback: 进度回调 (progress%, message)

        Returns:
            创建结果字典
        """
        # 1. 解析意图
        intent = self.intent_parser.parse(request)

        # 应用自定义覆盖
        if custom_data:
            if "output_format" in custom_data:
                intent.output_format = OutputFormat(custom_data["output_format"])
            if "title" in custom_data:
                intent.title = custom_data["title"]

        # 2. 构建上下文
        context = DocumentContext(
            intent=intent,
            custom_data=custom_data or {},
        )

        # 3. 创建任务
        task = self._create_task(WorkflowType.CREATE, context)

        # 4. 执行工作流
        try:
            result = await self.create_workflow.execute(context, progress_callback)
            task.result = result
            task.status = result.status
            task.completed_at = datetime.now().isoformat()

            # 5. 如果工作流完成，调用引擎渲染
            if result.status == WorkflowStatus.COMPLETED and result.output_data:
                engine_result = self._render_document(result.output_data, context)
                if engine_result:
                    result.output_path = engine_result.output_path

            # 6. 质量检查
            if result.output_path and os.path.exists(result.output_path):
                quality = self.quality_checker.check(
                    {"content": result.output_data.get("content", "")},
                    document_type=intent.document_type.value,
                )
                result.quality_score = quality.score / 100.0

        except Exception as e:
            task.status = WorkflowStatus.FAILED
            if task.result:
                task.result.errors.append(str(e))
            logger.error(f"创建文档失败: {e}")

        return task.to_dict()

    async def fill_document(self, template_path: str, fill_data: dict,
                            progress_callback: Callable = None) -> dict:
        """
        智能填充现有文档

        Args:
            template_path: 模板文件路径
            fill_data: 填充数据 {key: value}

        Returns:
            填充结果字典
        """
        # 构建上下文
        intent = DocumentIntent()
        context = DocumentContext(
            intent=intent,
            source_file=template_path,
            custom_data=fill_data,
        )

        task = self._create_task(WorkflowType.FILL_EDIT, context)

        try:
            result = await self.fill_edit_workflow.execute(context, progress_callback)
            task.result = result
            task.status = result.status
            task.completed_at = datetime.now().isoformat()

            # 执行引擎填充
            if result.status == WorkflowStatus.COMPLETED:
                ext = os.path.splitext(template_path)[1].lower()
                engine = EngineFactory.get_engine_for_format(ext.lstrip('.'))
                if engine:
                    output_path = self._generate_output_path(template_path, "_filled")
                    engine_result = engine.fill(template_path, fill_data, output_path)
                    if engine_result.success:
                        result.output_path = engine_result.output_path

        except Exception as e:
            task.status = WorkflowStatus.FAILED
            logger.error(f"填充文档失败: {e}")

        return task.to_dict()

    async def format_document(self, file_path: str, request: str = "",
                              theme_id: str = None,
                              progress_callback: Callable = None) -> dict:
        """
        格式化文档

        Args:
            file_path: 文档路径
            request: 格式化需求描述
            theme_id: 指定主题 ID

        Returns:
            格式化结果字典
        """
        intent = self.intent_parser.parse(request) if request else DocumentIntent()
        if theme_id:
            context_data = {"design_system_id": theme_id}
        else:
            context_data = {}

        context = DocumentContext(
            intent=intent,
            source_file=file_path,
            custom_data=context_data,
        )

        task = self._create_task(WorkflowType.FORMAT_APPLY, context)

        try:
            result = await self.format_apply_workflow.execute(context, progress_callback)
            task.result = result
            task.status = result.status
            task.completed_at = datetime.now().isoformat()

        except Exception as e:
            task.status = WorkflowStatus.FAILED
            logger.error(f"格式化文档失败: {e}")

        return task.to_dict()

    def analyze_intent(self, request: str) -> dict:
        """
        分析文档意图 (不执行，仅预览)

        Args:
            request: 自然语言需求

        Returns:
            意图分析结果 + 推荐模板 + 推荐主题
        """
        intent = self.intent_parser.parse(request)

        # 推荐模板
        template_match = self.template_router.route(
            document_type=intent.document_type.value,
            audience=intent.audience.value,
            importance=intent.importance.value,
            output_format=intent.output_format.value,
        )

        # 推荐主题
        theme_id = self.design_system.recommend_theme(
            intent.document_type.value, intent.audience.value
        )
        theme = self.design_system.get_theme(theme_id)

        # 推荐模型管线
        pipeline = self.model_router.route_pipeline([
            ModelCapability.DOCUMENT_PLANNING,
            ModelCapability.CONTENT_GENERATION,
            ModelCapability.FORMAT_UNDERSTANDING,
        ])

        return {
            "intent": intent.to_dict(),
            "recommended_template": template_match.to_dict(),
            "recommended_theme": {
                "id": theme_id,
                "name": theme.name,
            },
            "model_pipeline": {
                cap.value: model.to_dict()
                for cap, model in pipeline.items()
            },
        }

    def get_themes(self) -> list:
        """获取所有可用主题"""
        return self.design_system.list_themes()

    def get_templates(self, document_type: str = None) -> list:
        """获取可用模板"""
        return self.template_router.list_templates(document_type)

    def get_models(self, capability: str = None) -> list:
        """获取可用模型"""
        cap = ModelCapability(capability) if capability else None
        return self.model_router.list_models(cap)

    def check_dependencies(self) -> dict:
        """检查引擎依赖"""
        return EngineFactory.check_dependencies()

    def get_task(self, task_id: str) -> Optional[dict]:
        """获取任务"""
        task = self.tasks.get(task_id)
        return task.to_dict() if task else None

    def get_history(self, limit: int = 20) -> list:
        """获取任务历史"""
        tasks = sorted(
            self.tasks.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )
        return [t.to_dict() for t in tasks[:limit]]

    # ===== 🎨 格式理解 API =====

    def parse_format(self, file_path: str) -> dict:
        """
        解析文档格式

        Args:
            file_path: 文档路径

        Returns:
            格式信息字典
        """
        try:
            format_info = self.format_parser.parse(file_path)
            return format_info.to_dict()
        except Exception as e:
            logger.error(f"格式解析失败: {e}")
            return {"error": str(e)}

    def analyze_format_semantic(self, file_path: str) -> dict:
        """
        分析文档格式语义

        识别格式模式、业务语义、设计意图

        Args:
            file_path: 文档路径

        Returns:
            语义分析结果
        """
        try:
            # 解析格式
            format_info = self.format_parser.parse(file_path)

            # 构建格式图谱
            graph = FormatGraph()
            graph.build_from_elements(format_info.elements, format_info.styles)

            # 语义分析
            results = self.format_semantic.analyze(
                graph,
                [e.visual for e in format_info.elements],
                [e.structural for e in format_info.elements],
                [e.semantic for e in format_info.elements],
            )

            return results
        except Exception as e:
            logger.error(f"格式语义分析失败: {e}")
            return {"error": str(e)}

    def evaluate_format_quality(self, file_path: str) -> dict:
        """
        评估文档格式质量

        Args:
            file_path: 文档路径

        Returns:
            质量评估结果 + 改进建议
        """
        try:
            # 解析格式
            format_info = self.format_parser.parse(file_path)

            # 构建格式图谱
            graph = FormatGraph()
            graph.build_from_elements(format_info.elements, format_info.styles)

            # 质量评估
            metrics, improvements = self.format_evaluator.evaluate(format_info, graph)

            return {
                "metrics": metrics.to_dict(),
                "improvements": [i.to_dict() for i in improvements],
            }
        except Exception as e:
            logger.error(f"格式质量评估失败: {e}")
            return {"error": str(e)}

    async def generate_format_aware(self, requirement: str,
                                     format_constraints: dict,
                                     progress_callback: Callable = None) -> dict:
        """
        格式保持的内容生成

        在格式约束下生成内容，确保输出符合格式要求

        Args:
            requirement: 内容需求
            format_constraints: 格式约束字典
            progress_callback: 进度回调

        Returns:
            生成的内容 + 格式验证结果
        """
        from dataclasses import dataclass, field

        @dataclass
        class SimpleConstraint:
            max_length: int = 0
            font_name: str = ""
            font_size: float = 0.0
            alignment: str = ""
            semantic_role: str = ""
            must_include: list = field(default_factory=list)
            must_not_include: list = field(default_factory=list)

        constraints = SimpleConstraint(**format_constraints) if format_constraints else SimpleConstraint()

        result = await self.format_aware_workflow.format_aware_create(
            requirement=requirement,
            format_constraints=constraints,
            model_router=self.model_router,
            progress_callback=progress_callback,
        )

        return result

    async def migrate_format(self, source_file: str,
                            target_template: str,
                            progress_callback: Callable = None) -> dict:
        """
        智能格式迁移

        将内容从源文档迁移到目标模板，同时智能映射格式

        Args:
            source_file: 源文档路径
            target_template: 目标模板路径
            progress_callback: 进度回调

        Returns:
            迁移结果 + 格式映射
        """
        result = await self.format_aware_workflow.smart_format_migration(
            source_file=source_file,
            target_template=target_template,
            model_router=self.model_router,
            progress_callback=progress_callback,
        )

        return result

    def check_format_consistency(self, documents: List[str]) -> dict:
        """
        批量格式一致性检查

        Args:
            documents: 文档路径列表

        Returns:
            一致性检查结果 + 改进建议
        """
        result = self.format_aware_workflow.format_consistency_check(documents)
        return result

    def learn_user_format_preference(self, user_id: str, format_info: dict):
        """
        学习用户格式偏好

        Args:
            user_id: 用户ID
            format_info: 格式信息
        """
        self.format_knowledge.learn_preference(user_id, format_info)

    def get_user_format_preference(self, user_id: str) -> dict:
        """
        获取用户格式偏好

        Args:
            user_id: 用户ID

        Returns:
            用户偏好字典
        """
        pref = self.format_knowledge.get_user_preference(user_id)
        return pref.to_dict() if pref else {}

    # ===== 内部方法 =====

    def _create_task(self, workflow_type: WorkflowType,
                     context: DocumentContext) -> OfficeTask:
        """创建任务"""
        self._task_counter += 1
        task_id = f"office_{self._task_counter:06d}"
        task = OfficeTask(
            task_id=task_id,
            workflow_type=workflow_type,
            context=context,
        )
        self.tasks[task_id] = task
        return task

    def _render_document(self, output_data: dict,
                         context: DocumentContext) -> Any:
        """调用引擎渲染文档"""
        fmt = output_data.get("output_format", "docx")
        engine = EngineFactory.get_engine_for_format(fmt)

        if not engine:
            logger.warning(f"无可用引擎: {fmt}")
            return None

        output_path = self._generate_output_path(
            f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            suffix=f".{fmt}",
            base_dir=self.config.get("output_dir"),
        )

        if fmt == "docx":
            result = engine.create(
                title=output_data.get("outline", "").split('\n')[0][:50] if output_data.get("outline") else context.intent.title,
                content=output_data.get("content", ""),
                theme=output_data.get("theme"),
                output_path=output_path,
            )
        elif fmt == "pptx":
            result = engine.create(
                title=context.intent.title or "演示文稿",
                cover_style=output_data.get("template", {}).get("cover_style", "corporate"),
                output_path=output_path,
            )
        elif fmt == "xlsx":
            result = engine.create(
                title=context.intent.title or "数据表",
                output_path=output_path,
            )
        elif fmt == "pdf":
            result = engine.create(
                title=context.intent.title or "文档",
                content=output_data.get("content", ""),
                cover_style=output_data.get("template", {}).get("cover_style", "classic"),
                output_path=output_path,
            )
        else:
            return None

        return result if result.success else None

    def _generate_output_path(self, base_name: str, suffix: str = "",
                              base_dir: str = None) -> str:
        """生成输出路径"""
        if not base_dir:
            base_dir = os.path.join(
                os.path.expanduser("~"), "Documents", "HermesOffice"
            )
        os.makedirs(base_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{base_name}_{timestamp}{suffix}"
        return os.path.join(base_dir, filename)
