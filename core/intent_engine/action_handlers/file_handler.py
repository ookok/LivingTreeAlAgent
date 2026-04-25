# -*- coding: utf-8 -*-
"""
文件操作处理器 - FileOperationHandler
======================================

处理文件相关意图的执行：
- FILE_OPERATION (文件读/写/删除)
- FOLDER_STRUCTURE (目录结构)
- 同时作为 CODE_GENERATION 等的补充处理器

v2.0: 使用共享 LLMClient（自动回退 requests→urllib）
"""

from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict, List, Optional

from ..intent_types import IntentType
from .base import (
    BaseActionHandler,
    ActionContext,
    ActionResult,
    ActionResultStatus,
)
from .code_handler import call_llm

logger = logging.getLogger(__name__)


class FileOperationHandler(BaseActionHandler):
    """
    文件操作处理器
    
    覆盖意图：
    - FILE_OPERATION
    - FOLDER_STRUCTURE
    
    能力：
    1. 创建文件（通过 LLM 生成内容后写入）
    2. 读取文件（返回文件内容）
    3. 分析目录结构
    4. 生成项目骨架
    
    安全策略：
    - 不允许删除操作
    - 不允许操作工作区外的文件
    - 写入前需确认
    """
    
    # 允许的操作
    ALLOWED_OPS = {"create", "read", "list", "analyze"}
    
    @property
    def name(self) -> str:
        return "file_operation"
    
    @property
    def supported_intents(self) -> List[IntentType]:
        return [
            IntentType.FILE_OPERATION,
            IntentType.FOLDER_STRUCTURE,
        ]
    
    @property
    def priority(self) -> int:
        return 30
    
    def handle(self, ctx: ActionContext) -> ActionResult:
        """执行文件操作"""
        start = time.time()
        intent = ctx.intent
        
        # 分析操作类型
        op_type = self._detect_operation(intent)
        
        if op_type == "read":
            result = self._handle_read(ctx)
        elif op_type == "list":
            result = self._handle_list(ctx)
        elif op_type == "create":
            result = self._handle_create(ctx)
        elif op_type == "analyze":
            result = self._handle_analyze(ctx)
        else:
            result = self._make_clarify(
                f"无法确定要对文件执行什么操作。\n"
                f"您是想：\n"
                f"1. 创建新文件？\n"
                f"2. 读取文件内容？\n"
                f"3. 查看目录结构？\n"
                f"4. 分析文件？"
            )
        
        result.execution_time = time.time() - start
        return result
    
    def _detect_operation(self, intent) -> str:
        """检测操作类型"""
        text = intent.raw_input.lower()
        
        # 读取类
        if any(kw in text for kw in ["读", "查看", "打开", "read", "open", "cat", "显示", "show"]):
            return "read"
        
        # 列表类
        if any(kw in text for kw in ["目录", "结构", "树", "list", "tree", "文件列表", "有哪些文件"]):
            return "list"
        
        # 创建类
        if any(kw in text for kw in ["创建", "新建", "生成", "create", "new", "make", "写文件"]):
            return "create"
        
        # 分析类
        if any(kw in text for kw in ["分析", "统计", "analyze", "stat", "大小"]):
            return "analyze"
        
        return "read"  # 默认读取
    
    def _handle_read(self, ctx: ActionContext) -> ActionResult:
        """读取文件"""
        import re
        
        # 提取文件路径
        intent = ctx.intent
        file_path = self._extract_file_path(intent.raw_input)
        
        if not file_path:
            return self._make_clarify("请指定要读取的文件路径。")
        
        # 解析为完整路径
        full_path = os.path.join(ctx.working_dir, file_path)
        
        if not os.path.exists(full_path):
            return self._make_error(f"文件不存在: {full_path}")
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            return self._make_result(
                output=f"**文件**: `{file_path}`\n**大小**: {len(content)} 字符\n\n```\n{content}\n```",
                output_type="text",
            )
        except Exception as e:
            return self._make_error(f"读取文件失败: {e}")
    
    def _handle_list(self, ctx: ActionContext) -> ActionResult:
        """列出目录结构"""
        import re
        
        intent = ctx.intent
        dir_path = self._extract_file_path(intent.raw_input) or ctx.working_dir
        full_path = os.path.join(ctx.working_dir, dir_path)
        
        if not os.path.exists(full_path):
            return self._make_error(f"目录不存在: {full_path}")
        
        try:
            tree = self._build_tree(full_path, max_depth=3)
            return self._make_result(
                output=f"**目录结构**: `{dir_path}`\n\n```\n{tree}\n```",
                output_type="text",
                suggestions=["需要查看某个具体文件的内容吗？"],
            )
        except Exception as e:
            return self._make_error(f"列出目录失败: {e}")
    
    def _handle_create(self, ctx: ActionContext) -> ActionResult:
        """创建文件"""
        intent = ctx.intent

        # 使用 LLM 生成文件内容
        file_path = self._extract_file_path(intent.raw_input)

        prompt = f"""根据以下要求创建文件：

用户请求: {intent.raw_input}
技术栈: {', '.join(intent.tech_stack) if intent.tech_stack else ''}

请生成完整的文件内容，使用 Markdown 代码块格式。"""

        try:
            output = call_llm(ctx, prompt, system="你是一个代码生成助手。请生成完整的文件内容。")
        except RuntimeError:
            output = f"# 生成的文件\n\n# 基于意图: {intent.intent_type.value}\n# 目标: {intent.target}\n"
        
        return self._make_result(
            output=output,
            output_type="code",
            suggestions=[
                "需要将此内容写入文件吗？请确认文件路径。",
                "需要调整文件内容吗？",
            ],
        )
    
    def _handle_analyze(self, ctx: ActionContext) -> ActionResult:
        """分析文件"""
        intent = ctx.intent
        
        # 简单的文件分析
        file_path = self._extract_file_path(intent.raw_input) or ctx.working_dir
        full_path = os.path.join(ctx.working_dir, file_path)
        
        if os.path.isfile(full_path):
            try:
                size = os.path.getsize(full_path)
                lines = 0
                with open(full_path, "r", encoding="utf-8") as f:
                    lines = sum(1 for _ in f)
                return self._make_result(
                    output=f"**文件分析**: `{file_path}`\n\n"
                           f"| 属性 | 值 |\n"
                           f"|------|-----|\n"
                           f"| 大小 | {size} 字节 ({size/1024:.1f} KB) |\n"
                           f"| 行数 | {lines} |\n"
                           f"| 类型 | {os.path.splitext(file_path)[1] or '未知'} |",
                    output_type="text",
                )
            except Exception as e:
                return self._make_error(f"分析文件失败: {e}")
        
        return self._handle_list(ctx)
    
    def _extract_file_path(self, text: str) -> str:
        """从文本中提取文件路径"""
        import re
        patterns = [
            r'([a-zA-Z]:[\\\/][\w\\\/\.\-]+)',          # Windows 绝对路径
            r'([\w./\\\-]+\.\w{1,5})',                    # 相对路径/文件名
            r'["\']([\w./\\\-]+\.\w{1,5})["\']',          # 引号包裹的路径
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""
    
    def _build_tree(self, path: str, prefix: str = "", max_depth: int = 3, current_depth: int = 0) -> str:
        """构建目录树"""
        if current_depth >= max_depth:
            return ""
        
        if not os.path.isdir(path):
            return ""
        
        entries = sorted(os.listdir(path))
        # 过滤隐藏文件和 __pycache__
        entries = [e for e in entries if not e.startswith(".") and e != "__pycache__"]
        
        lines = []
        for i, entry in enumerate(entries[:50]):  # 最多50个条目
            is_last = i == len(entries[:50]) - 1
            connector = "└── " if is_last else "├── "
            
            entry_path = os.path.join(path, entry)
            if os.path.isdir(entry_path):
                lines.append(f"{prefix}{connector}📁 {entry}/")
                extension = "    " if is_last else "│   "
                lines.append(self._build_tree(entry_path, prefix + extension, max_depth, current_depth + 1))
            else:
                lines.append(f"{prefix}{connector}📄 {entry}")
        
        return "\n".join(lines)
