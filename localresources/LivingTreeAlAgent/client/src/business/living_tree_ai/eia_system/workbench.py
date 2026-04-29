"""
环评智能工作台 (EIA Workbench)
=============================

环评全流程自动化主入口，整合文档解析、计算、绘图、报告生成。
"""

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class ProjectStatus(Enum):
    """项目状态"""
    DRAFT = "draft"           # 草稿
    PARSING = "parsing"       # 解析中
    CALCULATING = "calculating"  # 计算中
    DRAWING = "drawing"       # 绘图中
    GENERATING = "generating"  # 报告生成中
    REVIEWING = "reviewing"   # 审核中
    COMPLETED = "completed"   # 完成


@dataclass
class ProjectConfig:
    """项目配置"""
    project_id: str
    name: str                          # 项目名称
    location: str = ""                  # 项目地点
    industry: str = ""                  # 行业类别
    scale: str = ""                     # 规模
    description: str = ""               # 项目描述

    # 输入文件路径
    feasibility_report: str = ""       # 可研报告
    layout_drawing: str = ""           # 总平面布置图
    equipment_list: str = ""           # 设备清单
    other_documents: list[str] = field(default_factory=list)

    # 计算参数
    air_dispersion_model: str = "AERMOD"  # 大气预测模型
    water_model: str = "Mike21"          # 水质预测模型
    noise_model: str = "CadnaA"          # 噪声预测模型

    # 输出配置
    output_format: str = "docx"          # 输出格式
    template: str = "standard"            # 报告模板

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: ProjectStatus = ProjectStatus.DRAFT


@dataclass
class WorkbenchState:
    """工作台状态"""
    project: ProjectConfig
    current_step: str = "idle"
    progress: float = 0                   # 0-1
    documents: dict = field(default_factory=dict)  # 解析的文档
    extracted_data: dict = field(default_factory=dict)  # 提取的数据
    calculation_results: dict = field(default_factory=dict)  # 计算结果
    drawings: dict = field(default_factory=dict)  # 图纸
    report_draft: str = ""               # 报告草稿
    compliance_results: list = field(default_factory=list)  # 合规检查结果
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class EIAWorkbench:
    """
    环评智能工作台

    用法:
        workbench = EIAWorkbench()

        # 创建项目
        project = workbench.create_project(
            name="某化工厂改扩建项目",
            industry="化工",
            location="江苏省南京市"
        )

        # 上传资料
        await workbench.upload_document(project.project_id, "可研报告.pdf")

        # 一键生成报告
        result = await workbench.generate_full_report(project.project_id)
    """

    def __init__(self, data_dir: str = "./data/eia"):
        self.data_dir = data_dir
        self._projects: dict[str, WorkbenchState] = {}
        self._document_parser = None
        self._calculator = None
        self._drawing_engine = None
        self._report_generator = None
        self._compliance_checker = None
        self._p2p_handler: Optional[Callable] = None
        self._ai_handler: Optional[Callable] = None

        # 确保目录存在
        os.makedirs(data_dir, exist_ok=True)

        # 创建子模块
        self._init_submodules()

    def _init_submodules(self) -> None:
        """初始化子模块"""
        from .document_parser import create_document_parser
        from .source_calculator import SourceCalculator
        from .drawing_engine import create_drawing_engine
        from .report_generator import create_report_generator
        from .compliance_checker import ComplianceChecker

        self._document_parser = create_document_parser(self.data_dir)
        self._calculator = SourceCalculator()
        self._drawing_engine = create_drawing_engine(self.data_dir)
        self._report_generator = create_report_generator(self.data_dir)
        self._compliance_checker = ComplianceChecker()

    def register_p2p_handler(self, handler: Callable) -> None:
        """注册 P2P 处理器"""
        self._p2p_handler = handler

    def register_ai_handler(self, handler: Callable) -> None:
        """注册 AI 处理器"""
        self._ai_handler = handler

    def create_project(self, name: str, industry: str = "", location: str = "", **kwargs) -> ProjectConfig:
        """
        创建新项目

        Args:
            name: 项目名称
            industry: 行业类别
            location: 项目地点
            **kwargs: 其他配置

        Returns:
            ProjectConfig: 项目配置
        """
        project_id = hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:12]

        project = ProjectConfig(
            project_id=project_id,
            name=name,
            industry=industry,
            location=location,
            **kwargs
        )

        self._projects[project_id] = WorkbenchState(project=project)

        return project

    def get_project(self, project_id: str) -> Optional[WorkbenchState]:
        """获取项目状态"""
        return self._projects.get(project_id)

    async def upload_document(self, project_id: str, file_path: str, doc_type: str = "auto") -> dict:
        """
        上传并解析文档

        Args:
            project_id: 项目 ID
            file_path: 文件路径
            doc_type: 文档类型 (feasibility/layout/equipment/auto)

        Returns:
            dict: 解析结果
        """
        state = self._projects.get(project_id)
        if not state:
            raise ValueError(f"Project not found: {project_id}")

        state.current_step = "parsing"
        state.project.status = ProjectStatus.PARSING

        try:
            # 解析文档
            parsed = await self._document_parser.parse(file_path, doc_type)

            # 存储解析结果
            state.documents[doc_type] = parsed
            state.extracted_data.update(parsed.extracted_data)

            state.progress = 0.2
            state.project.updated_at = datetime.now()

            return {
                "success": True,
                "doc_type": doc_type,
                "file_name": os.path.basename(file_path),
                "pages": parsed.page_count,
                "extracted_fields": list(parsed.extracted_data.keys())
            }

        except Exception as e:
            state.errors.append(f"文档解析失败: {str(e)}")
            return {"success": False, "error": str(e)}

    async def extract_pollution_sources(self, project_id: str) -> list[dict]:
        """
        从解析的文档中提取污染源

        Args:
            project_id: 项目 ID

        Returns:
            list[dict]: 污染源列表
        """
        state = self._projects.get(project_id)
        if not state:
            raise ValueError(f"Project not found: {project_id}")

        # 提取污染源数据
        sources = []

        # 从设备清单提取
        if "equipment" in state.documents:
            equip_data = state.documents["equipment"].extracted_data
            for equip in equip_data.get("equipment_list", []):
                source = self._calculator.identify_pollution_source(equip)
                if source:
                    sources.append(source)

        # 从工艺描述提取
        if "feasibility" in state.documents:
            feas_data = state.documents["feasibility"].extracted_data
            for process in feas_data.get("processes", []):
                source = self._calculator.identify_pollution_source(process)
                if source:
                    sources.append(source)

        state.extracted_data["pollution_sources"] = sources
        return sources

    async def calculate_source_strength(self, project_id: str) -> dict:
        """
        计算污染源源强

        Args:
            project_id: 项目 ID

        Returns:
            dict: 计算结果
        """
        state = self._projects.get(project_id)
        if not state:
            raise ValueError(f"Project not found: {project_id}")

        state.current_step = "calculating"
        state.project.status = ProjectStatus.CALCULATING

        sources = state.extracted_data.get("pollution_sources", [])

        results = {
            "air_sources": [],
            "water_sources": [],
            "noise_sources": [],
            "solid_waste_sources": []
        }

        for source in sources:
            calc_result = await self._calculator.calculate(source)
            results[f"{source.get('type', 'air')}_sources"].append(calc_result)

        state.calculation_results = results
        state.progress = 0.5
        state.project.updated_at = datetime.now()

        return results

    async def generate_drawings(self, project_id: str) -> dict:
        """
        生成图纸

        Args:
            project_id: 项目 ID

        Returns:
            dict: 生成的图纸
        """
        state = self._projects.get(project_id)
        if not state:
            raise ValueError(f"Project not found: {project_id}")

        state.current_step = "drawing"
        state.project.status = ProjectStatus.DRAWING

        drawings = {}

        # 1. 工艺流程图
        if state.extracted_data.get("processes"):
            flow_data = await self._drawing_engine.generate_flow_chart(
                project_name=state.project.name,
                processes=state.extracted_data["processes"],
                pollution_sources=state.extracted_data.get("pollution_sources", [])
            )
            drawings["process_flow"] = flow_data

        # 2. 总平面布置图
        if state.documents.get("layout"):
            layout_data = await self._drawing_engine.generate_layout(
                extracted_data=state.extracted_data
            )
            drawings["layout"] = layout_data

        # 3. 防护距离图
        protection_data = await self._drawing_engine.generate_protection_zones(
            pollution_sources=state.calculation_results.get("air_sources", []),
            building_outlines=state.extracted_data.get("buildings", [])
        )
        drawings["protection_zones"] = protection_data

        state.drawings = drawings
        state.progress = 0.75
        state.project.updated_at = datetime.now()

        return drawings

    async def generate_report(self, project_id: str) -> str:
        """
        生成报告

        Args:
            project_id: 项目 ID

        Returns:
            str: 报告文件路径
        """
        state = self._projects.get(project_id)
        if not state:
            raise ValueError(f"Project not found: {project_id}")

        state.current_step = "generating"
        state.project.status = ProjectStatus.GENERATING

        # 生成报告
        report_path = await self._report_generator.generate(
            project=state.project,
            documents=state.documents,
            extracted_data=state.extracted_data,
            calculation_results=state.calculation_results,
            drawings=state.drawings
        )

        state.report_draft = report_path
        state.progress = 0.95
        state.project.updated_at = datetime.now()

        return report_path

    async def check_compliance(self, project_id: str) -> list[dict]:
        """
        合规性检查

        Args:
            project_id: 项目 ID

        Returns:
            list[dict]: 合规检查结果
        """
        state = self._projects.get(project_id)
        if not state:
            raise ValueError(f"Project not found: {project_id}")

        # 执行合规检查
        results = await self._compliance_checker.check(
            project=state.project,
            data=state.extracted_data,
            calculation_results=state.calculation_results
        )

        state.compliance_results = results

        # 标记警告和错误
        state.warnings = [r for r in results if r.get("level") == "warning"]
        state.errors = [r for r in results if r.get("level") == "error"]

        return results

    async def generate_full_report(self, project_id: str) -> dict:
        """
        一键生成完整报告

        完整流程：上传资料 → 解析 → 提取污染源 → 计算 → 绘图 → 生成报告 → 合规检查

        Args:
            project_id: 项目 ID

        Returns:
            dict: 完整结果
        """
        state = self._projects.get(project_id)
        if not state:
            raise ValueError(f"Project not found: {project_id}")

        result = {
            "project_id": project_id,
            "project_name": state.project.name,
            "steps": [],
            "success": True,
            "output_path": ""
        }

        try:
            # Step 1: 提取污染源
            await self._step_append(result, "提取污染源",
                self.extract_pollution_sources(project_id))
            state.progress = 0.1

            # Step 2: 计算源强
            await self._step_append(result, "计算源强",
                self.calculate_source_strength(project_id))
            state.progress = 0.3

            # Step 3: 生成图纸
            await self._step_append(result, "生成图纸",
                self.generate_drawings(project_id))
            state.progress = 0.6

            # Step 4: 生成报告
            await self._step_append(result, "生成报告",
                self.generate_report(project_id))
            state.progress = 0.9

            # Step 5: 合规检查
            await self._step_append(result, "合规检查",
                self.check_compliance(project_id))

            state.project.status = ProjectStatus.COMPLETED
            state.progress = 1.0
            state.current_step = "completed"

            result["success"] = True
            result["output_path"] = state.report_draft
            result["drawings"] = list(state.drawings.keys())
            result["compliance"] = state.compliance_results
            result["warnings"] = state.warnings
            result["errors"] = state.errors

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            state.errors.append(str(e))

        return result

    async def _step_append(self, result: dict, step_name: str, coro) -> Any:
        """辅助方法：添加步骤到结果"""
        start_time = time.time()
        result_obj = await coro
        elapsed = time.time() - start_time

        result["steps"].append({
            "name": step_name,
            "success": True,
            "elapsed_seconds": round(elapsed, 2)
        })

        return result_obj

    def get_project_summary(self, project_id: str) -> dict:
        """获取项目摘要"""
        state = self._projects.get(project_id)
        if not state:
            return {"success": False, "error": "Project not found"}

        return {
            "success": True,
            "project_id": project_id,
            "name": state.project.name,
            "industry": state.project.industry,
            "status": state.project.status.value,
            "progress": state.progress,
            "current_step": state.current_step,
            "documents": list(state.documents.keys()),
            "pollution_sources_count": len(state.extracted_data.get("pollution_sources", [])),
            "drawings": list(state.drawings.keys()),
            "has_report": bool(state.report_draft),
            "warnings": len(state.warnings),
            "errors": len(state.errors),
            "created_at": state.project.created_at.isoformat(),
            "updated_at": state.project.updated_at.isoformat()
        }


def create_eia_workbench(data_dir: str = "./data/eia") -> EIAWorkbench:
    """创建环评工作台实例"""
    return EIAWorkbench(data_dir=data_dir)