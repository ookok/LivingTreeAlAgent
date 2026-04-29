"""
通用文档控制器

整合所有模块，提供端到端的通用文档协作体验。
"""

import json
import hashlib
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, AsyncGenerator
from enum import Enum
from datetime import datetime
from pathlib import Path

# 导入子模块
from .universal_template_engine import (
    UniversalDocumentTemplate,
    TemplateSchema,
    get_template_engine,
    load_template_async,
)
from .smart_field_renderer import (
    SmartFieldRenderer,
    get_field_renderer,
    render_field_async,
    render_form_async,
)
from .collaborative_document_engine import (
    CollaborativeDocumentEngine,
    Collaborator,
    DocumentOperation,
    OperationType,
    get_collaborative_engine,
    create_operation,
)
from .document_type_registry import (
    DocumentTypeRegistry,
    DocumentTypeInfo,
    DocumentCategory,
    get_document_types,
    get_document_type,
)
from .document_exporter import (
    DocumentExporter,
    DocumentExporterConfig,
    ExportFormat,
    ExportResult,
    get_exporter,
    export_document_async,
)


# ==================== 数据模型 ====================

class DocumentStatus(Enum):
    """文档状态"""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class DocumentMode(Enum):
    """文档模式"""
    CREATE = "create"
    EDIT = "edit"
    VIEW = "view"
    REVIEW = "review"
    COLLABORATIVE = "collaborative"


@dataclass
class Field:
    """文档字段"""
    id: str
    section_id: str
    value: Any = None
    original_value: Any = None
    is_modified: bool = False
    confidence: float = 0.0
    validation_status: str = "pending"
    ai_suggestion: Any = None


@dataclass
class Section:
    """文档章节"""
    id: str
    title: str
    content: Dict[str, Field] = field(default_factory=dict)
    is_expanded: bool = True
    is_completed: bool = False
    completion: float = 0.0


@dataclass
class Document:
    """文档"""
    id: str
    project_id: str
    type_id: str
    title: str
    status: DocumentStatus
    mode: DocumentMode
    sections: Dict[str, Section] = field(default_factory=dict)
    template: Optional[TemplateSchema] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""
    collaborators: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UniversalDocConfig:
    """通用文档配置"""
    default_type: str = "feasibility_report"
    enable_collaboration: bool = True
    enable_ai: bool = True
    auto_save: bool = True
    auto_save_interval: int = 30
    export_default_format: str = "html"


# ==================== 主控制器 ====================

class UniversalDocController:
    """
    通用文档主控制器

    整合模板、渲染、协作、导出等功能，提供端到端的文档体验。
    """

    def __init__(self, config: UniversalDocConfig = None):
        self.config = config or UniversalDocConfig()

        # 初始化子模块
        self.template_engine = get_template_engine()
        self.field_renderer = get_field_renderer()
        self.collab_engine = get_collaborative_engine()
        self.exporter = get_exporter()

        # 文档缓存
        self._documents: Dict[str, Document] = {}

        # 当前用户
        self._current_user: Optional[Collaborator] = None

    # ==================== 文档生命周期 ====================

    async def create_document(
        self,
        project_id: str,
        doc_type: str,
        title: str = None,
        created_by: str = None
    ) -> Document:
        """
        创建新文档

        Args:
            project_id: 项目ID
            doc_type: 文档类型
            title: 文档标题
            created_by: 创建人

        Returns:
            Document: 新建的文档
        """
        # 加载模板
        template = await load_template_async(doc_type)

        # 生成文档ID
        doc_id = self._generate_doc_id(project_id, doc_type)

        # 构建章节
        sections = {}
        for section_def in template.sections:
            section = Section(
                id=section_def.id,
                title=section_def.title,
                content={},
                is_expanded=True,
                is_completed=False,
                completion=0.0
            )

            # 构建字段
            for field_def in section_def.fields:
                section.content[field_def.id] = Field(
                    id=field_def.id,
                    section_id=section_def.id,
                    value=field_def.default_value,
                    original_value=None,
                    is_modified=False
                )

            sections[section_def.id] = section

        # 创建文档
        doc = Document(
            id=doc_id,
            project_id=project_id,
            type_id=doc_type,
            title=title or template.name,
            status=DocumentStatus.DRAFT,
            mode=DocumentMode.CREATE,
            sections=sections,
            template=template,
            created_by=created_by or "system"
        )

        self._documents[doc_id] = doc

        # 创建协作文档
        if self.config.enable_collaboration:
            await self.collab_engine.create_document(
                project_id=project_id,
                template_type=doc_type,
                initial_content=self._doc_to_content(doc)
            )

        return doc

    async def open_document(
        self,
        doc_id: str,
        mode: DocumentMode = DocumentMode.EDIT
    ) -> Optional[Document]:
        """
        打开文档

        Args:
            doc_id: 文档ID
            mode: 打开模式

        Returns:
            Optional[Document]: 文档
        """
        doc = self._documents.get(doc_id)
        if doc:
            doc.mode = mode
            doc.updated_at = datetime.now()
        return doc

    async def save_document(self, doc_id: str) -> bool:
        """
        保存文档

        Args:
            doc_id: 文档ID

        Returns:
            bool: 是否成功
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return False

        # 同步到协作引擎
        if self.config.enable_collaboration:
            await self.collab_engine.create_document(
                project_id=doc.project_id,
                template_type=doc.type_id,
                initial_content=self._doc_to_content(doc)
            )

        doc.updated_at = datetime.now()
        return True

    async def delete_document(self, doc_id: str) -> bool:
        """
        删除文档

        Args:
            doc_id: 文档ID

        Returns:
            bool: 是否成功
        """
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False

    # ==================== 字段操作 ====================

    async def update_field(
        self,
        doc_id: str,
        section_id: str,
        field_id: str,
        value: Any
    ) -> bool:
        """
        更新字段值

        Args:
            doc_id: 文档ID
            section_id: 章节ID
            field_id: 字段ID
            value: 新值

        Returns:
            bool: 是否成功
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return False

        section = doc.sections.get(section_id)
        if not section:
            return False

        field = section.content.get(field_id)
        if not field:
            return False

        # 记录原始值
        if field.original_value is None:
            field.original_value = field.value

        # 检查是否修改
        if field.value != value:
            field.is_modified = True

        field.value = value

        # 更新章节完成度
        self._update_section_completion(section)

        doc.updated_at = datetime.now()
        return True

    async def validate_field(
        self,
        doc_id: str,
        section_id: str,
        field_id: str
    ) -> Dict[str, Any]:
        """
        验证字段

        Args:
            doc_id: 文档ID
            section_id: 章节ID
            field_id: 字段ID

        Returns:
            Dict: 验证结果
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return {"valid": False, "error": "文档不存在"}

        section = doc.sections.get(section_id)
        if not section:
            return {"valid": False, "error": "章节不存在"}

        field = section.content.get(field_id)
        if not section:
            return {"valid": False, "error": "字段不存在"}

        # 获取字段定义
        field_def = None
        for s in doc.template.sections:
            if s.id == section_id:
                for f in s.fields:
                    if f.id == field_id:
                        field_def = f
                        break

        if not field_def:
            return {"valid": True}

        # 验证
        errors = []

        if field_def.required and not field.value:
            errors.append("必填字段不能为空")

        if field.value and field_def.field_type.value in ["number", "currency", "percentage"]:
            try:
                num_val = float(field.value)
                if field_def.min_value and num_val < field_def.min_value:
                    errors.append(f"值不能小于{field_def.min_value}")
                if field_def.max_value and num_val > field_def.max_value:
                    errors.append(f"值不能大于{field_def.max_value}")
            except ValueError:
                errors.append("请输入有效数字")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "field_id": field_id,
            "section_id": section_id
        }

    async def request_ai_suggestion(
        self,
        doc_id: str,
        section_id: str,
        field_id: str
    ) -> Optional[Any]:
        """
        请求AI建议

        Args:
            doc_id: 文档ID
            section_id: 章节ID
            field_id: 字段ID

        Returns:
            Any: AI建议
        """
        # 简化实现
        return None

    # ==================== 协作功能 ====================

    async def join_collaboration(
        self,
        doc_id: str,
        user: Collaborator
    ) -> bool:
        """
        加入协作

        Args:
            doc_id: 文档ID
            user: 协作者

        Returns:
            bool: 是否成功
        """
        self._current_user = user
        return await self.collab_engine.join_document(doc_id, user)

    async def leave_collaboration(self, doc_id: str):
        """离开协作"""
        if self._current_user:
            await self.collab_engine.leave_document(doc_id, self._current_user.id)

    async def apply_operation(
        self,
        doc_id: str,
        operation: DocumentOperation
    ) -> Dict[str, Any]:
        """
        应用协作操作

        Args:
            doc_id: 文档ID
            operation: 操作

        Returns:
            Dict: 操作结果
        """
        result = await self.collab_engine.apply_operation(doc_id, operation)

        if result.get("success"):
            # 更新本地文档
            doc = self._documents.get(doc_id)
            if doc and operation.field_id:
                field_parts = operation.field_id.split("_")
                section_id = field_parts[0] if len(field_parts) > 1 else ""
                field_id = "_".join(field_parts[1:]) if len(field_parts) > 1 else field_parts[0]

                if section_id in doc.sections:
                    field = doc.sections[section_id].content.get(field_id)
                    if field:
                        field.value = operation.new_value

        return result

    # ==================== 导出功能 ====================

    async def export_document(
        self,
        doc_id: str,
        format: str = "html"
    ) -> ExportResult:
        """
        导出文档

        Args:
            doc_id: 文档ID
            format: 导出格式

        Returns:
            ExportResult: 导出结果
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return ExportResult(
                success=False,
                format=ExportFormat.HTML,
                error="文档不存在"
            )

        # 转换为导出格式
        document_data = self._doc_to_export_data(doc)
        template_dict = self.template_engine.to_dict() if self.template_engine else {}

        return await export_document_async(document_data, template_dict, format)

    # ==================== 工具方法 ====================

    def _generate_doc_id(self, project_id: str, doc_type: str) -> str:
        """生成文档ID"""
        timestamp = datetime.now().isoformat()
        raw = f"{project_id}_{doc_type}_{timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _doc_to_content(self, doc: Document) -> Dict[str, Any]:
        """将文档转换为协作内容"""
        content = {}
        for section_id, section in doc.sections.items():
            section_content = {}
            for field_id, field in section.content.items():
                section_content[field_id] = field.value
            content[section_id] = section_content
        return content

    def _doc_to_export_data(self, doc: Document) -> Dict:
        """将文档转换为导出数据"""
        sections = []
        for section_def in doc.template.sections:
            section_data = doc.sections.get(section_def.id)
            section_content = {}

            if section_data:
                for field_def in section_def.fields:
                    field = section_data.content.get(field_def.id)
                    section_content[field_def.id] = field.value if field else None

            sections.append({
                "id": section_def.id,
                "title": section_def.title,
                "fields": section_def.fields,
                **section_content
            })

        return {
            "title": doc.title,
            "sections": sections,
            "metadata": {
                "type": doc.type_id,
                "status": doc.status.value,
                "created_at": doc.created_at.isoformat(),
                "updated_at": doc.updated_at.isoformat()
            }
        }

    def _update_section_completion(self, section: Section):
        """更新章节完成度"""
        total = len(section.content)
        if total == 0:
            section.completion = 0.0
            return

        completed = sum(
            1 for f in section.content.values()
            if f.value and f.value != ""
        )

        section.completion = completed / total
        section.is_completed = section.completion >= 1.0

    def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档"""
        return self._documents.get(doc_id)

    def get_all_documents(self, project_id: str = None) -> List[Document]:
        """获取所有文档"""
        docs = list(self._documents.values())
        if project_id:
            docs = [d for d in docs if d.project_id == project_id]
        return docs


# ==================== 便捷函数 ====================

_controller_instance: Optional[UniversalDocController] = None


def get_universal_controller(config: UniversalDocConfig = None) -> UniversalDocController:
    """获取控制器单例"""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = UniversalDocController(config)
    return _controller_instance


async def create_universal_doc(
    project_id: str,
    doc_type: str,
    title: str = None
) -> Document:
    """
    创建通用文档的便捷函数

    Args:
        project_id: 项目ID
        doc_type: 文档类型
        title: 文档标题

    Returns:
        Document: 新建的文档
    """
    controller = get_universal_controller()
    return await controller.create_document(project_id, doc_type, title)
