"""
环评增强服务 (EIAEnhancementService)
=====================================

核心思想：基于BrowserBridge和InjectionEngine，实现环评场景的智能增强

功能：
1. 智能填表 - 从数据库自动填充表单
2. 文档上传 - 环评报告、附件上传
3. 数据提取 - 从页面提取结构化数据
4. 审批跟踪 - 跟踪审批进度
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..eia_system import (
    EIAWorkbench,
    get_eia_workbench,
)


@dataclass
class FormAutoFill:
    """自动填表数据"""
    form_id: str
    fields: List[Dict[str, str]]
    confidence: float = 0.0
    source: str = ""  # 数据来源


@dataclass
class UploadTask:
    """上传任务"""
    task_id: str
    file_type: str  # 环评报告/附件/图纸
    file_name: str
    status: str = "pending"  # pending/uploading/completed/failed
    progress: float = 0.0
    error: str = ""


class EIAEnhancementService:
    """
    环评增强服务

    与BrowserBridge配合，实现：
    1. 智能填表
    2. 文档上传
    3. 数据提取
    4. 审批跟踪
    """

    def __init__(self):
        # 环评工作台
        self.eia_workbench: Optional[EIAWorkbench] = None

        # 企业数据库（从环评报告提取的企业信息）
        self.company_db: Dict[str, Dict] = {}

        # 自动填表规则
        self.autofill_rules: Dict[str, FormAutoFill] = {}

        # 上传任务
        self.upload_tasks: Dict[str, UploadTask] = {}

        # 初始化
        self._init_autofill_rules()

    def set_eia_workbench(self, workbench: EIAWorkbench):
        """设置环评工作台"""
        self.eia_workbench = workbench

    def _init_autofill_rules(self):
        """初始化自动填表规则"""
        # 环保局网站表单字段映射
        self.autofill_rules = {
            "project_name": {
                "fields": [
                    {"name": "projectName", "label": "项目名称"},
                    {"name": " constructionUnit", "label": "建设单位"},
                    {"name": "region", "label": "所在地区"},
                ]
            },
            "company_info": {
                "fields": [
                    {"name": "companyName", "label": "企业名称"},
                    {"name": "legalPerson", "label": "法人代表"},
                    {"name": "contactPerson", "label": "联系人"},
                    {"name": "contactPhone", "label": "联系电话"},
                ]
            },
            "pollution_info": {
                "fields": [
                    {"name": "airPollutants", "label": "废气污染物"},
                    {"name": "waterPollutants", "label": "废水污染物"},
                    {"name": "solidWastes", "label": "固体废物"},
                ]
            }
        }

    # ============ 智能填表 ============

    async def get_autofill_data(
        self,
        url: str,
        form_data: Dict[str, Any]
    ) -> FormAutoFill:
        """
        获取自动填表数据

        Args:
            url: 页面URL
            form_data: 表单数据

        Returns:
            FormAutoFill: 自动填表数据
        """
        # 1. 匹配URL模式
        rule = self._match_url_rule(url)

        # 2. 查找企业信息
        company_info = self._find_company_info(form_data)

        # 3. 构建填充字段
        fields = []

        if rule:
            for field_def in rule.get("fields", []):
                field_name = field_def["name"]
                value = company_info.get(field_name, "")
                if value:
                    fields.append({
                        "name": field_name,
                        "value": value,
                        "confidence": 0.9
                    })

        # 4. 如果没有匹配规则，尝试智能匹配
        if not fields:
            fields = await self._smart_match_fields(form_data, company_info)

        return FormAutoFill(
            form_id=rule.get("id", "unknown") if rule else "smart",
            fields=fields,
            confidence=len(fields) / max(len(form_data.get("fields", [])), 1),
            source="company_db" if company_info else "ai_inference"
        )

    def _match_url_rule(self, url: str) -> Optional[Dict]:
        """匹配URL规则"""
        url_patterns = {
            "sthjj.gov.cn": "company_info",
            "mee.gov.cn/permit": "pollution_info",
            "eia.gov.cn": "project_name",
        }

        for pattern, rule_id in url_patterns.items():
            if pattern in url:
                return self.autofill_rules.get(rule_id)
        return None

    def _find_company_info(self, form_data: Dict) -> Dict:
        """查找企业信息"""
        # 从表单字段推断
        field_names = [f.get("name", "") for f in form_data.get("fields", [])]

        # 匹配企业数据库
        for company_id, company in self.company_db.items():
            # 简单匹配
            if any("company" in f.lower() for f in field_names):
                return company

        return {}

    async def _smart_match_fields(
        self,
        form_data: Dict,
        company_info: Dict
    ) -> List[Dict[str, str]]:
        """智能匹配字段"""
        fields = []
        form_fields = form_data.get("fields", [])

        # 字段名关键词映射
        keyword_map = {
            "项目名称": ["projectName", "project_name", "项目名称"],
            "建设单位": ["companyName", "company_name", "建设单位", " constructionUnit"],
            "联系人": ["contactPerson", "contact_person", "联系人"],
            "电话": ["contactPhone", "contact_phone", "联系电话", "phone"],
        }

        for form_field in form_fields:
            field_name = form_field.get("name", "")
            field_label = form_field.get("label", "")

            # 关键词匹配
            for keyword, aliases in keyword_map.items():
                if keyword in field_label:
                    for alias in aliases:
                        if alias in company_info:
                            fields.append({
                                "name": field_name,
                                "value": company_info[alias],
                                "confidence": 0.8
                            })
                            break

        return fields

    def save_company_info(self, company_id: str, info: Dict):
        """保存企业信息"""
        self.company_db[company_id] = info

    # ============ 文档上传 ============

    async def upload_document(
        self,
        file_path: str,
        upload_url: str,
        file_type: str = "attachment"
    ) -> UploadTask:
        """
        上传文档

        Args:
            file_path: 文件路径
            upload_url: 上传URL
            file_type: 文件类型

        Returns:
            UploadTask: 上传任务
        """
        task_id = f"upload_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        task = UploadTask(
            task_id=task_id,
            file_type=file_type,
            file_name=file_path.split("/")[-1].split("\\")[-1],
            status="uploading",
            progress=0.0
        )
        self.upload_tasks[task_id] = task

        try:
            # 模拟上传过程
            import aiohttp

            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as f:
                    file_data = f.read()

                form_data = aiohttp.FormData()
                form_data.add_field('file', file_data, filename=task.file_name, content_type='application/octet-stream')

                async with session.post(upload_url, data=form_data) as resp:
                    if resp.status == 200:
                        task.status = "completed"
                        task.progress = 100.0
                    else:
                        task.status = "failed"
                        task.error = f"HTTP {resp.status}"

        except Exception as e:
            task.status = "failed"
            task.error = str(e)

        return task

    def get_upload_task(self, task_id: str) -> Optional[UploadTask]:
        """获取上传任务状态"""
        return self.upload_tasks.get(task_id)

    # ============ 数据提取 ============

    async def extract_page_data(
        self,
        url: str,
        html: str
    ) -> Dict[str, Any]:
        """
        从页面提取结构化数据

        Args:
            url: 页面URL
            html: 页面HTML

        Returns:
            Dict: 结构化数据
        """
        data = {
            "url": url,
            "extracted_at": datetime.now().isoformat(),
            "tables": [],
            "forms": [],
            "links": [],
            "metadata": {}
        }

        # 提取表格
        table_pattern = r'<table[^>]*>(.*?)</table>'
        tables = re.findall(table_pattern, html, re.DOTALL | re.IGNORECASE)
        for i, table in enumerate(tables[:10]):  # 最多10个
            data["tables"].append({
                "index": i,
                "rows": self._extract_table_rows(table),
                "headers": self._extract_table_headers(table)
            })

        # 提取表单
        form_pattern = r'<form[^>]*>(.*?)</form>'
        forms = re.findall(form_pattern, html, re.DOTALL | re.IGNORECASE)
        for i, form in enumerate(forms):
            data["forms"].append({
                "index": i,
                "fields": self._extract_form_fields(form)
            })

        # 提取链接
        link_pattern = r'<a[^>]+href="([^"]+)"[^>]*>([^<]*)</a>'
        links = re.findall(link_pattern, html)
        data["links"] = [{"url": l[0], "text": l[1]} for l in links[:50]]

        return data

    def _extract_table_rows(self, table_html: str) -> List[List[str]]:
        """提取表格行"""
        rows = []
        row_pattern = r'<tr[^>]*>(.*?)</tr>'
        row_matches = re.findall(row_pattern, table_html, re.DOTALL | re.IGNORECASE)
        for row in row_matches[:20]:  # 最多20行
            cell_pattern = r'<t[dh][^>]*>(.*?)</t[dh]>'
            cells = re.findall(cell_pattern, row, re.DOTALL | re.IGNORECASE)
            clean_cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            rows.append(clean_cells)
        return rows

    def _extract_table_headers(self, table_html: str) -> List[str]:
        """提取表头"""
        header_pattern = r'<th[^>]*>(.*?)</th>'
        headers = re.findall(header_pattern, table_html, re.DOTALL | re.IGNORECASE)
        return [re.sub(r'<[^>]+>', '', h).strip() for h in headers]

    def _extract_form_fields(self, form_html: str) -> List[Dict]:
        """提取表单字段"""
        fields = []

        # input
        input_pattern = r'<input[^>]+name="([^"]+)"[^>]*>'
        for match in re.finditer(input_pattern, form_html):
            fields.append({"name": match.group(1), "type": "input"})

        # select
        select_pattern = r'<select[^>]+name="([^"]+)"'
        for match in re.finditer(select_pattern, form_html):
            fields.append({"name": match.group(1), "type": "select"})

        # textarea
        textarea_pattern = r'<textarea[^>]+name="([^"]+)"'
        for match in re.finditer(textarea_pattern, form_html):
            fields.append({"name": match.group(1), "type": "textarea"})

        return fields

    # ============ 审批跟踪 ============

    async def track_approval_progress(
        self,
        project_id: str,
        approval_url: str
    ) -> Dict[str, Any]:
        """
        跟踪审批进度

        Args:
            project_id: 项目ID
            approval_url: 审批查询URL

        Returns:
            Dict: 审批进度信息
        """
        # 模拟审批进度查询
        progress = {
            "project_id": project_id,
            "current_stage": "技术评审",
            "stages": [
                {"name": "受理", "status": "completed", "date": "2024-01-15"},
                {"name": "形式审查", "status": "completed", "date": "2024-01-18"},
                {"name": "技术评审", "status": "in_progress", "date": ""},
                {"name": "审批决定", "status": "pending", "date": ""},
            ],
            "estimated_completion": "2024-02-15",
            "issues": []
        }

        return progress


# 全局实例
_eia_service_instance: Optional[EIAEnhancementService] = None


def get_eia_enhancement_service() -> EIAEnhancementService:
    """获取环评增强服务全局实例"""
    global _eia_service_instance
    if _eia_service_instance is None:
        _eia_service_instance = EIAEnhancementService()
    return _eia_service_instance