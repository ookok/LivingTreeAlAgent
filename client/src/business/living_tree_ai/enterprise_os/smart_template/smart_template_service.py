"""
智能模板服务 (Smart Template Service)

统一入口，整合文档结构提取、AI推理模板、数据驱动渲染三大模块，
实现"文档 → 模板 + 数据 → 新文档"的全自动流程。

核心功能：
1. 模板生成：从定稿文档自动推理模板配置
2. 模板管理：模板的存储、版本、复用
3. 报告生成：数据驱动渲染生成新报告
4. 迭代优化：用户修正反馈自动优化模板

使用示例：
```python
service = SmartTemplateService()

# 1. 从定稿文档生成模板
template = await service.generate_template(
    source_doc="环评报告定稿.docx",
    document_type="environmental_assessment",
    domain_hint="环保"
)

# 2. 保存模板
await service.save_template(template, "templates/eia_template.json")

# 3. 生成新报告
result = await service.generate_report(
    template_config="templates/eia_template.json",
    project_data={
        "company_name": "XX化工有限公司",
        "monitoring_data": [...]
    },
    output_path="output/新项目环评报告.docx"
)
```
"""

import json
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

class TemplateStatus(Enum):
    """模板状态"""
    DRAFT = "draft"           # 草稿（刚生成未校验）
    VALIDATED = "validated"   # 已校验（人工确认）
    ACTIVE = "active"        # 激活（正在使用）
    DEPRECATED = "deprecated" # 已废弃


@dataclass
class TemplateMetadata:
    """模板元数据"""
    template_id: str
    template_name: str
    document_type: str  # 报告类型
    domain: str  # 领域（环保/安全/能源等）
    version: str = "1.0.0"
    status: TemplateStatus = TemplateStatus.DRAFT
    source_checksum: str = ""  # 源文档校验和
    source_file: str = ""
    created_at: str = ""
    updated_at: str = ""
    usage_count: int = 0  # 使用次数
    author: str = "AI"
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "document_type": self.document_type,
            "domain": self.domain,
            "version": self.version,
            "status": self.status.value,
            "source_checksum": self.source_checksum,
            "source_file": self.source_file,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "author": self.author,
            "description": self.description
        }


@dataclass
class TemplateFeedback:
    """用户反馈"""
    feedback_id: str
    template_id: str
    project_id: str  # 关联的项目
    data_key: str  # 被修正的数据键
    original_value: Any  # AI 生成的值
    corrected_value: Any  # 用户修正的值
    corrected_by: str = ""  # 修正人
    corrected_at: str = ""  # 修正时间
    notes: str = ""  # 备注

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "template_id": self.template_id,
            "project_id": self.project_id,
            "data_key": self.data_key,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "corrected_by": self.corrected_by,
            "corrected_at": self.corrected_at,
            "notes": self.notes
        }


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool
    output_path: Optional[str] = None
    template_id: str = ""
    project_id: str = ""
    stats: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output_path": self.output_path,
            "template_id": self.template_id,
            "project_id": self.project_id,
            "stats": self.stats,
            "message": self.message,
            "warnings": self.warnings
        }


# ==================== 智能模板服务 ====================

class SmartTemplateService:
    """
    智能模板服务

    统一入口，提供：
    1. 模板生成 - 从定稿文档推理模板
    2. 模板管理 - CRUD 操作
    3. 报告生成 - 数据驱动渲染
    4. 反馈学习 - 用户修正自动优化
    """

    def __init__(
        self,
        template_dir: str = "templates",
        llm_callable: Optional[Callable] = None
    ):
        """
        初始化服务

        Args:
            template_dir: 模板存储目录
            llm_callable: LLM 调用函数，用于更智能的模板推理
        """
        self._template_dir = Path(template_dir)
        self._llm = llm_callable
        self._templates: Dict[str, Dict[str, Any]] = {}  # 内存缓存

        # 延迟导入子模块
        self._extractor = None
        self._engine = None
        self._renderer = None

    @property
    def extractor(self):
        """懒加载文档结构提取器"""
        if self._extractor is None:
            from .document_struct_extractor import DocumentStructExtractor
            self._extractor = DocumentStructExtractor()
        return self._extractor

    @property
    def engine(self):
        """懒加载 AI 模板引擎"""
        if self._engine is None:
            from .ai_template_engine import AITemplateEngine
            self._engine = AITemplateEngine(self._llm)
        return self._engine

    @property
    def renderer(self):
        """懒加载数据驱动渲染器"""
        if self._renderer is None:
            from .data_driven_renderer import DataDrivenRenderer
            self._renderer = DataDrivenRenderer()
        return self._renderer

    async def generate_template(
        self,
        source_doc: str,
        document_type: str = "",
        domain_hint: str = "environmental_assessment",
        save_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从定稿文档生成模板配置

        Args:
            source_doc: 定稿文档路径（.docx）
            document_type: 文档类型（环评/安评/能评等）
            domain_hint: 领域提示
            save_path: 保存路径（可选）

        Returns:
            Dict: 模板配置（包含 metadata 和 config）
        """
        logger.info(f"开始从文档生成模板: {source_doc}")

        # 步骤1: 提取文档结构
        logger.info("步骤1: 提取文档结构...")
        ast = await self.extractor.extract(source_doc)
        ast_dict = ast.to_dict()
        logger.info(f"  - 提取完成: {ast.total_paragraphs} 段落, {ast.total_tables} 表格")

        # 步骤2: AI 推理模板
        logger.info("步骤2: AI 推理模板骨架...")
        template_config = await self.engine.infer_template(
            ast_dict,
            document_type=document_type,
            domain_hint=domain_hint
        )
        logger.info(f"  - 推理完成: {len(template_config.blocks)} 块, {len(template_config.tables)} 表格")

        # 构建完整模板（包含元数据）
        now = datetime.now().isoformat()
        full_template = {
            "metadata": {
                "template_id": template_config.template_id,
                "template_name": template_config.template_name,
                "document_type": document_type,
                "domain": domain_hint,
                "version": "1.0.0",
                "status": "draft",
                "source_checksum": ast.checksum,
                "source_file": source_doc,
                "created_at": now,
                "updated_at": now,
                "usage_count": 0,
                "author": "AI",
                "description": f"从 {Path(source_doc).name} 自动推理生成"
            },
            "config": template_config.to_dict()
        }

        # 保存模板
        if save_path:
            self._template_dir.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(full_template, f, ensure_ascii=False, indent=2)
            logger.info(f"模板已保存到: {save_path}")

        return full_template

    async def generate_report(
        self,
        template_config: Union[str, Dict[str, Any]],
        project_data: Dict[str, Any],
        output_path: str,
        project_id: str = "",
        context: Optional[Dict[str, Any]] = None
    ) -> GenerationResult:
        """
        生成报告

        Args:
            template_config: 模板配置（路径或 dict）
            project_data: 项目数据
            output_path: 输出路径
            project_id: 项目 ID
            context: 额外上下文

        Returns:
            GenerationResult: 生成结果
        """
        logger.info(f"开始生成报告: {output_path}")

        # 加载模板
        if isinstance(template_config, str):
            with open(template_config, 'r', encoding='utf-8') as f:
                template_config = json.load(f)

        # 提取 config 部分
        config = template_config.get('config', template_config)
        metadata = template_config.get('metadata', {})

        # 渲染文档
        from .data_driven_renderer import RenderContext, OutputFormat, get_data_driven_renderer

        render_context = RenderContext(
            project_id=project_id,
            project_name=project_data.get('project_name', ''),
            generated_at=datetime.now().isoformat(),
            extra=context or {}
        )

        # 根据输出格式选择
        output_format = OutputFormat.HTML
        if output_path.endswith('.docx'):
            output_format = OutputFormat.DOCX
        elif output_path.endswith('.md'):
            output_format = OutputFormat.MARKDOWN
        elif output_path.endswith('.json'):
            output_format = OutputFormat.JSON

        renderer = get_data_driven_renderer()
        result = await renderer.render(
            config,
            project_data,
            output_path=output_path,
            output_format=output_format,
            context=render_context
        )

        # 更新使用统计
        if result.success:
            template_id = metadata.get('template_id', '')
            if template_id:
                await self._increment_usage(template_id)

        return GenerationResult(
            success=result.success,
            output_path=result.output_path,
            template_id=metadata.get('template_id', ''),
            project_id=project_id,
            stats=result.stats,
            message=result.message,
            warnings=[]
        )

    async def validate_template(
        self,
        template_path: str,
        validator: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        校验模板

        Args:
            template_path: 模板路径
            validator: 校验函数（可选）

        Returns:
            Dict: 校验结果
        """
        with open(template_path, 'r', encoding='utf-8') as f:
            template = json.load(f)

        config = template.get('config', {})
        blocks = config.get('blocks', [])
        tables = config.get('tables', [])

        issues = []

        # 检查必要字段
        for block in blocks:
            if block.get('block_type') == 'dynamic' and not block.get('data_key'):
                issues.append(f"块 {block.get('block_id')} 缺少 data_key")

        # 检查表格
        for table in tables:
            if not table.get('data_key'):
                issues.append(f"表格 {table.get('table_id')} 缺少 data_key")

        # 如果提供了自定义校验器，执行校验
        if validator:
            custom_issues = await validator(template)
            issues.extend(custom_issues)

        # 更新状态
        if not issues:
            template['metadata']['status'] = 'validated'
            with open(template_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, ensure_ascii=False, indent=2)

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "template_id": template.get('metadata', {}).get('template_id')
        }

    async def learn_from_feedback(
        self,
        feedback: TemplateFeedback
    ) -> bool:
        """
        从用户反馈学习，优化模板

        Args:
            feedback: 用户反馈

        Returns:
            bool: 是否成功
        """
        logger.info(f"学习反馈: {feedback.data_key} {feedback.original_value} → {feedback.corrected_value}")

        # TODO: 实现反馈学习机制
        # 1. 记录反馈到反馈池
        # 2. 分析反馈模式
        # 3. 调整模板推理规则
        # 4. 可选：重新推理模板

        return True

    async def list_templates(
        self,
        domain: Optional[str] = None,
        status: Optional[TemplateStatus] = None
    ) -> List[Dict[str, Any]]:
        """
        列出模板

        Args:
            domain: 领域筛选
            status: 状态筛选

        Returns:
            List[Dict]: 模板列表
        """
        templates = []

        if self._template_dir.exists():
            for path in self._template_dir.glob("*.json"):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        template = json.load(f)
                    metadata = template.get('metadata', {})

                    # 筛选
                    if domain and metadata.get('domain') != domain:
                        continue
                    if status and metadata.get('status') != status.value:
                        continue

                    templates.append(metadata)
                except Exception as e:
                    logger.warning(f"加载模板失败 {path}: {e}")

        return templates

    async def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """获取模板"""
        templates = await self.list_templates()
        for t in templates:
            if t.get('template_id') == template_id:
                # 加载完整配置
                for path in self._template_dir.glob("*.json"):
                    with open(path, 'r', encoding='utf-8') as f:
                        template = json.load(f)
                    if template.get('metadata', {}).get('template_id') == template_id:
                        return template
        return None

    async def _increment_usage(self, template_id: str):
        """增加使用计数"""
        for path in self._template_dir.glob("*.json"):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    template = json.load(f)
                if template.get('metadata', {}).get('template_id') == template_id:
                    template['metadata']['usage_count'] = template['metadata'].get('usage_count', 0) + 1
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(template, f, ensure_ascii=False, indent=2)
                    break
            except Exception as e:
                logger.warning(f"更新使用计数失败: {e}")


# ==================== 便捷函数 ====================

_service: Optional[SmartTemplateService] = None


def get_smart_template_service(
    template_dir: str = "templates",
    llm_callable: Optional[Callable] = None
) -> SmartTemplateService:
    """获取服务单例"""
    global _service
    if _service is None:
        _service = SmartTemplateService(template_dir, llm_callable)
    return _service


async def generate_template_from_document(
    source_doc: str,
    document_type: str = "",
    domain_hint: str = "environmental_assessment"
) -> Dict[str, Any]:
    """从文档生成模板"""
    service = get_smart_template_service()
    return await service.generate_template(source_doc, document_type, domain_hint)


async def generate_report_from_template(
    template_config: Union[str, Dict[str, Any]],
    project_data: Dict[str, Any],
    output_path: str,
    project_id: str = ""
) -> GenerationResult:
    """从模板生成报告"""
    service = get_smart_template_service()
    return await service.generate_report(template_config, project_data, output_path, project_id)