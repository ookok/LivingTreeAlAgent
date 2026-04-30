# -*- coding: utf-8 -*-
"""
Integrated Tools - PageIndex + OfficeCLI 无缝集成
=================================================
实现"知识获取 → 内容生成 → 文档落地"完整闭环

工具分工:
- PageIndex: 文档智能解析 + 推理检索
- OfficeCLI: 本地 Office 文档自动化编辑
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ToolType(Enum):
    PAGEINDEX = "pageindex"
    OFFICECLI = "officecli"
    OLLAMA = "ollama"


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    citations: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class IntegratedTools:
    """
    PageIndex + OfficeCLI 集成工具
    实现"知识获取 → 内容生成 → 文档落地"完整闭环
    """

    _instance: Optional['IntegratedTools'] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self.pageindex = None
        self.officecli_path: Optional[str] = None
        self._initialized = False
        self._init_task: Optional[asyncio.Task] = None

    @classmethod
    async def get_instance(cls) -> 'IntegratedTools':
        """获取单例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance._async_init()
        return cls._instance

    async def _async_init(self):
        """异步初始化"""
        if self._initialized:
            return

        try:
            # 1. 初始化 OfficeCLI
            from utils.officecli_setup import ensure_officecli
            loop = asyncio.get_event_loop()
            self.officecli_path = await loop.run_in_executor(None, ensure_officecli)
            logger.info(f"OfficeCLI 已就绪: {self.officecli_path}")

            # 2. 初始化 PageIndex
            from business.page_index import get_pageindex_tool
            self.pageindex = get_pageindex_tool()
            logger.info("PageIndex 已就绪")

            self._initialized = True
        except Exception as e:
            logger.error(f"集成工具初始化失败: {e}")
            raise

    def is_ready(self) -> bool:
        """检查是否就绪"""
        return self._initialized and self.pageindex is not None and self.officecli_path is not None


class WorkflowEngine:
    """
    工作流引擎 - 协调 PageIndex + Ollama + OfficeCLI
    """

    def __init__(self, integrated_tools: IntegratedTools):
        self.tools = integrated_tools

    async def execute_knowledge_to_document(
        self,
        question: str,
        document_path: str,
        operation: str,
        data: Dict[str, Any]
    ) -> WorkflowResult:
        """
        完整工作流: 知识获取 → 内容生成 → 文档落地

        Args:
            question: 用户问题
            document_path: 目标文档路径
            operation: OfficeCLI 操作 (create/set/add)
            data: 操作数据

        Returns:
            WorkflowResult: 执行结果
        """
        result = WorkflowResult(success=False, message="")

        try:
            # Step 1: PageIndex 查询
            if self.tools.pageindex and self.tools.pageindex.is_indexed():
                query_result = await self.tools.pageindex.query_and_answer(question)
                result.data["pageindex_result"] = query_result
                result.citations = query_result.get("citations", [])

                if not query_result.get("answer"):
                    result.errors.append("PageIndex 未找到相关内容")

            # Step 2: OfficeCLI 执行
            if self.tools.officecli_path:
                from utils.officecli_run import run_officecli_cli

                # 构建命令
                cmd = [operation, document_path]
                for key, value in data.items():
                    cmd.extend([f"--{key}", str(value)])

                loop = asyncio.get_event_loop()
                stdout, stderr, code = await loop.run_in_executor(
                    None,
                    lambda: run_officecli_cli(self.tools.officecli_path, cmd)
                )

                if code == 0:
                    result.data["office_output"] = stdout
                    result.success = True
                    result.message = f"文档操作成功: {document_path}"
                else:
                    result.errors.append(f"OfficeCLI 错误: {stderr}")
                    result.message = f"文档操作失败: {stderr}"

            return result

        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            result.errors.append(str(e))
            result.message = f"工作流执行失败: {e}"
            return result

    async def query_and_generate(
        self,
        question: str,
        context_docs: List[str] = None
    ) -> WorkflowResult:
        """
        查询 + 生成工作流

        Args:
            question: 用户问题
            context_docs: 上下文文档列表

        Returns:
            WorkflowResult: 包含答案和引用
        """
        result = WorkflowResult(success=False, message="")

        try:
            if not self.tools.pageindex:
                result.message = "PageIndex 未初始化"
                return result

            # PageIndex 查询
            query_result = await self.tools.pageindex.query_and_answer(
                question,
                context_docs=context_docs
            )

            result.data["answer"] = query_result.get("answer", "")
            result.data["raw_result"] = query_result
            result.citations = query_result.get("citations", [])
            result.success = True
            result.message = "查询成功"

            return result

        except Exception as e:
            logger.error(f"查询生成失败: {e}")
            result.errors.append(str(e))
            result.message = f"查询失败: {e}"
            return result


# 全局实例
_integrated_tools: Optional[IntegratedTools] = None
_workflow_engine: Optional[WorkflowEngine] = None


async def get_integrated_tools() -> IntegratedTools:
    """获取集成工具单例"""
    global _integrated_tools
    if _integrated_tools is None:
        _integrated_tools = await IntegratedTools.get_instance()
    return _integrated_tools


async def get_workflow_engine() -> WorkflowEngine:
    """获取工作流引擎"""
    global _workflow_engine
    tools = await get_integrated_tools()
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine(tools)
    return _workflow_engine


# ============= Hermes Tool 集成 =============

async def query_knowledge_base(question: str, context_docs: List[str] = None) -> Dict[str, Any]:
    """
    Hermes Tool: 查询知识库 (PageIndex)

    用法:
        query_knowledge_base("如何配置认证？")
    """
    engine = await get_workflow_engine()
    result = await engine.query_and_generate(question, context_docs)

    return {
        "success": result.success,
        "answer": result.data.get("answer", ""),
        "citations": result.citations,
        "message": result.message,
        "errors": result.errors
    }


async def modify_office_document(
    document_path: str,
    operation: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Hermes Tool: 修改 Office 文档 (OfficeCLI)

    用法:
        modify_office_document("report.xlsx", "set", {"cell": "A1", "value": "100"})
    """
    tools = await get_integrated_tools()

    if not tools.officecli_path:
        return {
            "success": False,
            "error": "OfficeCLI 未初始化"
        }

    try:
        from utils.officecli_run import run_officecli_cli

        cmd = [operation, document_path]
        for key, value in data.items():
            cmd.extend([f"--{key}", str(value)])

        loop = asyncio.get_event_loop()
        stdout, stderr, code = await loop.run_in_executor(
            None,
            lambda: run_officecli_cli(tools.officecli_path, cmd)
        )

        return {
            "success": code == 0,
            "output": stdout,
            "error": stderr if code != 0 else None
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def knowledge_to_document_workflow(
    question: str,
    document_path: str,
    operation: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Hermes Tool: 完整工作流 (PageIndex → Ollama → OfficeCLI)

    用法:
        knowledge_to_document_workflow(
            "请根据手册添加风险评估表",
            "report.xlsx",
            "add",
            {"sheet": "风险评估", "rows": "3"}
        )
    """
    engine = await get_workflow_engine()
    result = await engine.execute_knowledge_to_document(
        question, document_path, operation, data
    )

    return {
        "success": result.success,
        "message": result.message,
        "citations": result.citations,
        "data": result.data,
        "errors": result.errors
    }


async def batch_office_operations(commands: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Hermes Tool: 批量 Office 操作

    用法:
        batch_office_operations([
            {"command": "view", "args": ["doc.docx", "text"]},
            {"command": "set", "args": ["doc.docx", "paragraph", "--text", "新内容"]}
        ])
    """
    tools = await get_integrated_tools()

    if not tools.officecli_path:
        return {
            "success": False,
            "error": "OfficeCLI 未初始化"
        }

    try:
        from utils.officecli_run import batch_edit_json

        loop = asyncio.get_event_loop()
        stdout, stderr, code = await loop.run_in_executor(
            None,
            lambda: batch_edit_json(tools.officecli_path, commands)
        )

        return {
            "success": code == 0,
            "output": stdout,
            "error": stderr if code != 0 else None
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def register_integrated_tools_to_hermes(hermes_agent):
    """
    注册集成工具到 Hermes Agent

    在 Hermes 的 agent.py 或 tools.py 中调用:
        from business.integrated_tools import register_integrated_tools_to_hermes
        register_integrated_tools_to_hermes(hermes_agent)
    """
    from hermes.tool import tool

    # 注册为 Hermes 工具
    hermes_agent.register_tool("query_knowledge_base", query_knowledge_base)
    hermes_agent.register_tool("modify_office_document", modify_office_document)
    hermes_agent.register_tool("knowledge_to_document", knowledge_to_document_workflow)
    hermes_agent.register_tool("batch_office_ops", batch_office_operations)

    logger.info("集成工具已注册到 Hermes")
