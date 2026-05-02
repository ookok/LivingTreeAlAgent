"""
数字咨询工程师 - 核心控制器

整合文档解析、代码生成、文档生成、形式化验证等模块，
提供完整的咨询文档自动化生成能力。
"""
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..document_parser.models import ParsedDocument
from ..document_parser.parser_engine import DocumentParserFactory
from ..sica_engine.sica_engine import SICACodeGenerator, CodeGenerationResult
from ..document_generator.document_generator import DocumentGenerator, DocumentGenerationResult
from ..formal_verification.verification_engine import FormalVerifier, VerificationReport

logger = logging.getLogger(__name__)


class ProjectType(Enum):
    """项目类型"""
    EIA = "eia"                    # 环境影响评价
    FEASIBILITY_STUDY = "feasibility"  # 可行性研究
    FINANCIAL_ANALYSIS = "financial"    # 财务分析
    TECHNICAL_DESIGN = "technical"      # 技术设计
    CUSTOM = "custom"                  # 自定义


class TaskType(Enum):
    """任务类型"""
    PARSE_DOCUMENT = "parse_document"
    GENERATE_CODE = "generate_code"
    GENERATE_REPORT = "generate_report"
    VERIFY_DATA = "verify_data"
    FULL_PIPELINE = "full_pipeline"


@dataclass
class ProjectContext:
    """项目上下文"""
    project_id: str
    project_name: str
    project_type: ProjectType
    input_files: List[str] = field(default_factory=list)
    parsed_documents: List[ParsedDocument] = field(default_factory=list)
    generated_code: Dict[str, str] = field(default_factory=dict)
    generated_reports: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str
    task_type: TaskType
    success: bool
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class ConsultingEngineer:
    """
    数字咨询工程师
    
    核心能力：
    1. 解析环评/可研等咨询文档
    2. 根据文档内容生成Python计算代码
    3. 生成结构化的Word/PDF报告
    4. 验证关键数据的准确性
    5. 端到端自动化流水线
    """
    
    def __init__(self):
        self.document_parser = DocumentParserFactory()
        self.code_generator = SICACodeGenerator()
        self.document_generator = DocumentGenerator()
        self.verifier = FormalVerifier()
        
        # 项目上下文缓存
        self.project_contexts: Dict[str, ProjectContext] = {}
    
    def create_project(self, project_name: str, project_type: str) -> ProjectContext:
        """
        创建新项目
        
        Args:
            project_name: 项目名称
            project_type: 项目类型
        
        Returns:
            ProjectContext
        """
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        project_type_enum = self._parse_project_type(project_type)
        
        context = ProjectContext(
            project_id=project_id,
            project_name=project_name,
            project_type=project_type_enum,
        )
        
        self.project_contexts[project_id] = context
        logger.info(f"Created project: {project_id} - {project_name}")
        
        return context
    
    def get_project(self, project_id: str) -> Optional[ProjectContext]:
        """获取项目上下文"""
        return self.project_contexts.get(project_id)
    
    def delete_project(self, project_id: str):
        """删除项目"""
        if project_id in self.project_contexts:
            del self.project_contexts[project_id]
            logger.info(f"Deleted project: {project_id}")
    
    def parse_documents(self, project_id: str, file_paths: List[str]) -> TaskResult:
        """
        解析文档
        
        Args:
            project_id: 项目ID
            file_paths: 文件路径列表
        
        Returns:
            TaskResult
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        context = self.get_project(project_id)
        
        if not context:
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.PARSE_DOCUMENT,
                success=False,
                errors=["项目不存在"]
            )
        
        parsed_docs = []
        errors = []
        
        for file_path in file_paths:
            try:
                doc = self.document_parser.create_parser(file_path).parse(file_path)
                parsed_docs.append(doc)
                context.input_files.append(file_path)
                logger.info(f"Parsed document: {file_path}")
            except Exception as e:
                errors.append(f"解析文件失败 {file_path}: {e}")
                logger.error(f"Failed to parse {file_path}: {e}")
        
        context.parsed_documents = parsed_docs
        
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.PARSE_DOCUMENT,
            success=len(errors) == 0,
            message=f"成功解析 {len(parsed_docs)} 份文档",
            data={
                "document_count": len(parsed_docs),
                "documents": [doc.document_id for doc in parsed_docs],
            },
            errors=errors,
        )
    
    async def generate_code(self, project_id: str, requirements: Dict[str, Any]) -> TaskResult:
        """
        生成代码
        
        Args:
            project_id: 项目ID
            requirements: 代码生成需求
        
        Returns:
            TaskResult
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        context = self.get_project(project_id)
        
        if not context:
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.GENERATE_CODE,
                success=False,
                errors=["项目不存在"]
            )
        
        try:
            # 构建任务描述
            task_description = self._build_task_description(context, requirements)
            
            # 生成代码
            result = await self.code_generator.generate_code(task_description, requirements)
            
            if result.success:
                code_key = f"code_{len(context.generated_code) + 1}"
                context.generated_code[code_key] = {
                    "code": result.code,
                    "test_code": result.test_code,
                    "description": task_description,
                }
                
                logger.info(f"Generated code for project: {project_id}")
                
                return TaskResult(
                    task_id=task_id,
                    task_type=TaskType.GENERATE_CODE,
                    success=True,
                    message="代码生成成功",
                    data={
                        "code_key": code_key,
                        "code_length": len(result.code),
                        "test_exists": bool(result.test_code),
                        "confidence": result.confidence,
                    },
                    warnings=result.warnings,
                )
            else:
                return TaskResult(
                    task_id=task_id,
                    task_type=TaskType.GENERATE_CODE,
                    success=False,
                    message="代码生成失败",
                    errors=result.errors,
                )
        
        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.GENERATE_CODE,
                success=False,
                errors=[str(e)]
            )
    
    def generate_report(self, project_id: str, output_path: str, format: str = "docx") -> TaskResult:
        """
        生成报告
        
        Args:
            project_id: 项目ID
            output_path: 输出路径
            format: 输出格式 (docx/md)
        
        Returns:
            TaskResult
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        context = self.get_project(project_id)
        
        if not context:
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.GENERATE_REPORT,
                success=False,
                errors=["项目不存在"]
            )
        
        try:
            # 根据项目类型选择报告生成方式
            if context.project_type == ProjectType.EIA:
                result = self.document_generator.generate_eia_report(context.data, output_path)
            elif context.project_type == ProjectType.FEASIBILITY_STUDY:
                result = self.document_generator.generate_feasibility_study(context.data, output_path)
            else:
                # 自定义报告
                result = self.document_generator.generate_from_schema(
                    schema=None,  # 会使用默认schema
                    data=context.data,
                    output_path=output_path,
                    format=format,
                )
            
            if result.success:
                context.generated_reports.append(output_path)
                logger.info(f"Generated report: {output_path}")
                
                return TaskResult(
                    task_id=task_id,
                    task_type=TaskType.GENERATE_REPORT,
                    success=True,
                    message=f"报告生成成功: {output_path}",
                    data={
                        "output_path": output_path,
                        "sections_count": result.generated_sections,
                    },
                    warnings=result.warnings,
                )
            else:
                return TaskResult(
                    task_id=task_id,
                    task_type=TaskType.GENERATE_REPORT,
                    success=False,
                    message="报告生成失败",
                    errors=result.errors,
                )
        
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.GENERATE_REPORT,
                success=False,
                errors=[str(e)]
            )
    
    def verify_data(self, project_id: str) -> TaskResult:
        """
        验证数据
        
        Args:
            project_id: 项目ID
        
        Returns:
            TaskResult
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        context = self.get_project(project_id)
        
        if not context:
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.VERIFY_DATA,
                success=False,
                errors=["项目不存在"]
            )
        
        try:
            # 根据项目类型选择验证方式
            if context.project_type == ProjectType.EIA:
                report = self.verifier.verify_eia_data(context.data)
            elif context.project_type == ProjectType.FEASIBILITY_STUDY or context.project_type == ProjectType.FINANCIAL_ANALYSIS:
                report = self.verifier.verify_financial_data(context.data)
            else:
                # 使用通用验证
                report = VerificationReport(
                    success=True,
                    total_checks=0,
                    passed_checks=0,
                    failed_checks=0,
                    warnings=0,
                )
            
            # 收集失败的验证结果
            failed_results = [r for r in report.results if r.status.value == "failed"]
            warnings = [r.message for r in report.results if r.status.value == "warning"]
            
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.VERIFY_DATA,
                success=report.success,
                message=f"验证完成: {report.passed_checks}/{report.total_checks} 通过",
                data={
                    "total_checks": report.total_checks,
                    "passed_checks": report.passed_checks,
                    "failed_checks": report.failed_checks,
                    "pass_rate": report.pass_rate,
                    "failed_items": [r.message for r in failed_results],
                },
                errors=[r.message for r in failed_results],
                warnings=warnings,
            )
        
        except Exception as e:
            logger.error(f"Data verification failed: {e}")
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.VERIFY_DATA,
                success=False,
                errors=[str(e)]
            )
    
    async def run_full_pipeline(self, project_id: str, output_dir: str) -> TaskResult:
        """
        运行完整流水线
        
        Args:
            project_id: 项目ID
            output_dir: 输出目录
        
        Returns:
            TaskResult
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        context = self.get_project(project_id)
        
        if not context:
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.FULL_PIPELINE,
                success=False,
                errors=["项目不存在"]
            )
        
        logger.info(f"Starting full pipeline for project: {project_id}")
        
        try:
            # 步骤1: 验证数据
            verify_result = self.verify_data(project_id)
            if not verify_result.success:
                return TaskResult(
                    task_id=task_id,
                    task_type=TaskType.FULL_PIPELINE,
                    success=False,
                    message="数据验证失败",
                    errors=verify_result.errors,
                )
            
            # 步骤2: 生成代码
            code_result = await self.generate_code(project_id, {})
            if not code_result.success:
                return TaskResult(
                    task_id=task_id,
                    task_type=TaskType.FULL_PIPELINE,
                    success=False,
                    message="代码生成失败",
                    errors=code_result.errors,
                )
            
            # 步骤3: 生成报告
            output_path = str(Path(output_dir) / f"{context.project_name}.docx")
            report_result = self.generate_report(project_id, output_path)
            if not report_result.success:
                return TaskResult(
                    task_id=task_id,
                    task_type=TaskType.FULL_PIPELINE,
                    success=False,
                    message="报告生成失败",
                    errors=report_result.errors,
                )
            
            # 保存代码文件
            for code_key, code_info in context.generated_code.items():
                code_path = str(Path(output_dir) / f"{code_key}.py")
                with open(code_path, "w", encoding="utf-8") as f:
                    f.write(code_info["code"])
                
                if code_info.get("test_code"):
                    test_path = str(Path(output_dir) / f"test_{code_key}.py")
                    with open(test_path, "w", encoding="utf-8") as f:
                        f.write(code_info["test_code"])
            
            logger.info(f"Full pipeline completed successfully: {project_id}")
            
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.FULL_PIPELINE,
                success=True,
                message="流水线执行完成",
                data={
                    "report_path": output_path,
                    "code_files": list(context.generated_code.keys()),
                    "verify_pass_rate": verify_result.data.get("pass_rate", 0),
                },
            )
        
        except Exception as e:
            logger.error(f"Full pipeline failed: {e}")
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.FULL_PIPELINE,
                success=False,
                errors=[str(e)]
            )
    
    def set_project_data(self, project_id: str, data: Dict[str, Any]):
        """设置项目数据"""
        context = self.get_project(project_id)
        if context:
            context.data.update(data)
    
    def _parse_project_type(self, project_type: str) -> ProjectType:
        """解析项目类型"""
        mapping = {
            "eia": ProjectType.EIA,
            "环评": ProjectType.EIA,
            "feasibility": ProjectType.FEASIBILITY_STUDY,
            "可研": ProjectType.FEASIBILITY_STUDY,
            "financial": ProjectType.FINANCIAL_ANALYSIS,
            "财务": ProjectType.FINANCIAL_ANALYSIS,
            "technical": ProjectType.TECHNICAL_DESIGN,
            "技术": ProjectType.TECHNICAL_DESIGN,
        }
        return mapping.get(project_type.lower(), ProjectType.CUSTOM)
    
    def _build_task_description(self, context: ProjectContext, requirements: Dict[str, Any]) -> str:
        """构建任务描述"""
        parts = []
        
        # 项目类型
        type_names = {
            ProjectType.EIA: "环境影响评价",
            ProjectType.FEASIBILITY_STUDY: "可行性研究",
            ProjectType.FINANCIAL_ANALYSIS: "财务分析",
            ProjectType.TECHNICAL_DESIGN: "技术设计",
        }
        parts.append(f"项目类型：{type_names.get(context.project_type, '自定义')}")
        parts.append(f"项目名称：{context.project_name}")
        
        # 添加数据字段信息
        if context.data:
            parts.append("\n数据字段：")
            for key, value in context.data.items():
                if isinstance(value, (int, float)):
                    parts.append(f"- {key}: {value}")
        
        # 添加额外需求
        if requirements:
            parts.append("\n额外需求：")
            for key, value in requirements.items():
                parts.append(f"- {key}: {value}")
        
        return "\n".join(parts)


# 单例模式
_consulting_engineer = None


def get_consulting_engineer() -> ConsultingEngineer:
    """获取咨询工程师单例"""
    global _consulting_engineer
    if _consulting_engineer is None:
        _consulting_engineer = ConsultingEngineer()
    return _consulting_engineer


# 便捷函数
def create_eia_project(project_name: str) -> ProjectContext:
    """创建环评项目"""
    engineer = get_consulting_engineer()
    return engineer.create_project(project_name, "eia")


def create_feasibility_project(project_name: str) -> ProjectContext:
    """创建可研项目"""
    engineer = get_consulting_engineer()
    return engineer.create_project(project_name, "feasibility")


async def process_eia_document(project_id: str, file_path: str, output_dir: str) -> TaskResult:
    """处理环评文档的便捷函数"""
    engineer = get_consulting_engineer()
    
    # 解析文档
    parse_result = engineer.parse_documents(project_id, [file_path])
    if not parse_result.success:
        return parse_result
    
    # 运行完整流水线
    return await engineer.run_full_pipeline(project_id, output_dir)