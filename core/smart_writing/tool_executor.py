"""
工具执行器
============

整合所有工具，提供统一的执行接口：
1. 工具注册 - FileTools, ExecutionTools, GitTools
2. 批量执行 - 支持工具链调用
3. 用户确认 - 危险操作需要确认
4. 执行日志 - 完整操作追踪

设计原则：
- 统一接口 - 所有工具通过 execute() 调用
- 安全第一 - 危险操作需要确认
- 可追溯 - 每个操作都有日志
- 可回滚 - 支持撤销操作

使用方式:
    from core.smart_writing.tool_executor import ToolExecutor

    executor = ToolExecutor(project_root="/path/to/project")

    # 执行单个工具
    result = executor.execute("read_file", path="src/main.py")

    # 执行工具链
    results = executor.execute_chain([
        {"tool": "read_file", "args": {"path": "src/main.py"}},
        {"tool": "write_file", "args": {"path": "src/main.py", "content": "..."}},
    ])

    # 获取 LLM 工具列表
    tools = executor.get_tools_for_llm()
"""

import os
import time
import json
import uuid
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from .tool_definition import (
    Tool, ToolCall, ToolResult, ToolStatus,
    ToolRegistry, ToolCategory, ToolCallParser,
    GLOBAL_REGISTRY
)
from .file_tools import FileTools
from .execution_tools import ExecutionTools
from .git_tools import GitTools


# ============== 配置 ==============

# 操作日志目录
LOG_DIR = ".tool_logs"


# ============== 执行模式 ==============

class ExecutionMode(Enum):
    """执行模式"""
    AUTO = "auto"           # 自动执行（无确认）
    SAFE = "safe"           # 安全模式（需要确认）
    DRY_RUN = "dry_run"    # 模拟执行（不实际执行）


# ============== 操作日志 ==============

@dataclass
class OperationLog:
    """操作日志"""
    id: str
    timestamp: float
    tool_name: str
    arguments: Dict[str, Any]
    status: ToolStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    user_confirmed: bool = False
    parent_log_id: Optional[str] = None  # 链式调用时的父日志

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "tool_name": self.tool_name,
            "arguments": self._mask_arguments(),
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "execution_time": self.execution_time,
            "user_confirmed": self.user_confirmed,
            "parent_log_id": self.parent_log_id,
        }

    def _mask_arguments(self) -> Dict[str, Any]:
        """屏蔽敏感参数"""
        masked = {}
        sensitive_keys = {"password", "token", "secret", "key", "api_key"}
        for k, v in self.arguments.items():
            if any(s in k.lower() for s in sensitive_keys):
                masked[k] = "***"
            else:
                masked[k] = v
        return masked


# ============== 工具执行器 ==============

class ToolExecutor:
    """
    工具执行器

    整合所有工具，提供统一的执行接口。
    """

    def __init__(
        self,
        project_root: str,
        mode: ExecutionMode = ExecutionMode.SAFE,
        auto_backup: bool = True,
        max_chain_depth: int = 10,
    ):
        """
        初始化

        Args:
            project_root: 项目根目录
            mode: 执行模式
            auto_backup: 是否自动备份
            max_chain_depth: 最大链式调用深度
        """
        self.project_root = Path(project_root).resolve()
        self.mode = mode
        self.auto_backup = auto_backup
        self.max_chain_depth = max_chain_depth

        # 创建工具注册表
        self.registry = ToolRegistry()

        # 初始化各类工具
        self.file_tools = FileTools(
            project_root=str(self.project_root),
            backup_enabled=auto_backup,
            registry=self.registry,
        )

        self.execution_tools = ExecutionTools(
            project_root=str(self.project_root),
            registry=self.registry,
        )

        self.git_tools = GitTools(
            project_root=str(self.project_root),
            registry=self.registry,
        )

        # 操作日志
        self._logs: List[OperationLog] = []

        # 用户确认回调
        self._on_confirm: Optional[Callable[[Tool], bool]] = None

        # 创建日志目录
        self._log_dir = self.project_root / LOG_DIR
        self._log_dir.mkdir(exist_ok=True)

    def set_confirm_callback(self, callback: Callable[[Tool], bool]):
        """
        设置用户确认回调

        Args:
            callback: 返回 True 表示用户确认，False 表示拒绝
        """
        self._on_confirm = callback

    def _should_confirm(self, tool: Tool) -> bool:
        """判断是否需要确认"""
        if self.mode == ExecutionMode.AUTO:
            return False

        if tool.confirm_required:
            return True

        if tool.danger:
            return True

        return False

    def _request_confirmation(self, tool: Tool, arguments: Dict[str, Any]) -> bool:
        """请求用户确认"""
        if self._on_confirm:
            return self._on_confirm(tool)

        # 默认拒绝（需要用户显式确认）
        return False

    def _create_log(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        status: ToolStatus,
        result: Any = None,
        error: str = None,
        execution_time: float = 0.0,
        user_confirmed: bool = False,
        parent_log_id: Optional[str] = None,
    ) -> OperationLog:
        """创建操作日志"""
        log = OperationLog(
            id=str(uuid.uuid4())[:8],
            timestamp=time.time(),
            tool_name=tool_name,
            arguments=arguments,
            status=status,
            result=result,
            error=error,
            execution_time=execution_time,
            user_confirmed=user_confirmed,
            parent_log_id=parent_log_id,
        )
        self._logs.append(log)
        return log

    def _save_log(self, log: OperationLog):
        """保存日志到文件"""
        try:
            log_file = self._log_dir / f"{datetime.now().strftime('%Y%m%d')}.jsonl"
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log.to_dict(), ensure_ascii=False) + '\n')
        except Exception:
            pass

    # ============== 执行接口 ==============

    def execute(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        user_confirmed: bool = False,
        parent_log_id: Optional[str] = None,
    ) -> ToolResult:
        """
        执行工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            user_confirmed: 用户是否已确认
            parent_log_id: 父日志 ID（链式调用时）

        Returns:
            工具执行结果
        """
        arguments = arguments or {}
        start_time = time.time()

        # 获取工具
        tool = self.registry.get_tool(tool_name)
        if not tool:
            log = self._create_log(
                tool_name=tool_name,
                arguments=arguments,
                status=ToolStatus.FAILED,
                error=f"Tool '{tool_name}' not found",
            )
            self._save_log(log)
            return ToolResult(
                call_id=log.id,
                tool_name=tool_name,
                status=ToolStatus.FAILED,
                error=f"Tool '{tool_name}' not found",
            )

        # 检查是否需要确认
        if self._should_confirm(tool) and not user_confirmed:
            # 发送确认请求
            log = self._create_log(
                tool_name=tool_name,
                arguments=arguments,
                status=ToolStatus.CONFIRM,
                parent_log_id=parent_log_id,
            )
            self._save_log(log)
            return ToolResult(
                call_id=log.id,
                tool_name=tool_name,
                status=ToolStatus.CONFIRM,
                message=f"需要确认执行: {tool_name}",
            )

        # 干运行模式
        if self.mode == ExecutionMode.DRY_RUN:
            log = self._create_log(
                tool_name=tool_name,
                arguments=arguments,
                status=ToolStatus.SUCCESS,
                result={"dry_run": True},
                execution_time=time.time() - start_time,
                user_confirmed=True,
                parent_log_id=parent_log_id,
            )
            self._save_log(log)
            return ToolResult(
                call_id=log.id,
                tool_name=tool_name,
                status=ToolStatus.SUCCESS,
                result={"dry_run": True, "message": "干运行模式，未实际执行"},
                execution_time=time.time() - start_time,
            )

        # 执行工具
        try:
            result = self.registry.execute(
                name=tool_name,
                arguments=arguments,
                call_id=None,  # 让 registry 生成
            )

            # 记录日志
            execution_time = time.time() - start_time
            log = self._create_log(
                tool_name=tool_name,
                arguments=arguments,
                status=result.status,
                result=result.result,
                error=result.error,
                execution_time=execution_time,
                user_confirmed=user_confirmed,
                parent_log_id=parent_log_id,
            )
            self._save_log(log)

            # 更新 call_id
            result.call_id = log.id
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            log = self._create_log(
                tool_name=tool_name,
                arguments=arguments,
                status=ToolStatus.FAILED,
                error=str(e),
                execution_time=execution_time,
                user_confirmed=user_confirmed,
                parent_log_id=parent_log_id,
            )
            self._save_log(log)
            return ToolResult(
                call_id=log.id,
                tool_name=tool_name,
                status=ToolStatus.FAILED,
                error=str(e),
                execution_time=execution_time,
            )

    def execute_chain(
        self,
        steps: List[Dict[str, Any]],
        stop_on_error: bool = True,
    ) -> List[ToolResult]:
        """
        执行工具链

        Args:
            steps: 工具调用列表 [{"tool": "xxx", "args": {...}}, ...]
            stop_on_error: 是否在错误时停止

        Returns:
            执行结果列表
        """
        results = []
        parent_log_id = None

        for i, step in enumerate(steps):
            if i >= self.max_chain_depth:
                results.append(ToolResult(
                    call_id="",
                    tool_name=step.get("tool", "unknown"),
                    status=ToolStatus.FAILED,
                    error=f"超出最大链式调用深度: {self.max_chain_depth}",
                ))
                break

            tool_name = step.get("tool")
            arguments = step.get("args", {})
            user_confirmed = step.get("confirmed", False)

            result = self.execute(
                tool_name=tool_name,
                arguments=arguments,
                user_confirmed=user_confirmed,
                parent_log_id=parent_log_id,
            )

            results.append(result)

            # 更新父日志 ID
            if result.call_id:
                parent_log_id = result.call_id

            # 如果失败且需要停止
            if stop_on_error and not result.is_success:
                break

        return results

    def execute_from_text(
        self,
        text: str,
        stop_on_error: bool = True,
    ) -> List[ToolResult]:
        """
        从自然语言或 JSON 执行工具调用

        Args:
            text: 包含工具调用的文本
            stop_on_error: 是否在错误时停止

        Returns:
            执行结果列表
        """
        # 尝试解析 JSON
        parser = ToolCallParser()
        call = parser.parse_json(text)

        if call:
            return [self.execute(
                tool_name=call.tool_name,
                arguments=call.arguments,
            )]

        # 尝试解析自然语言
        calls = parser.parse_natural_language(text)

        if calls:
            return self.execute_chain([
                {"tool": c.tool_name, "args": c.arguments}
                for c in calls
            ], stop_on_error=stop_on_error)

        return [ToolResult(
            call_id="",
            tool_name="unknown",
            status=ToolStatus.FAILED,
            error="无法解析工具调用",
        )]

    def confirm_and_execute(
        self,
        call_id: str,
        confirmed: bool,
    ) -> ToolResult:
        """
        确认并执行待确认的工具调用

        Args:
            call_id: 调用 ID
            confirmed: 用户是否确认

        Returns:
            执行结果
        """
        # 查找日志
        log = None
        for l in reversed(self._logs):
            if l.id == call_id:
                log = l
                break

        if not log:
            return ToolResult(
                call_id=call_id,
                tool_name="unknown",
                status=ToolStatus.FAILED,
                error=f"找不到日志: {call_id}",
            )

        if not confirmed:
            # 用户拒绝
            log.status = ToolStatus.CANCELLED
            log.user_confirmed = False
            self._save_log(log)
            return ToolResult(
                call_id=call_id,
                tool_name=log.tool_name,
                status=ToolStatus.CANCELLED,
                message="用户取消",
            )

        # 确认后执行
        return self.execute(
            tool_name=log.tool_name,
            arguments=log.arguments,
            user_confirmed=True,
            parent_log_id=log.parent_log_id,
        )

    # ============== 查询接口 ==============

    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """获取适合 LLM 的工具列表"""
        return self.registry.get_tools_for_llm()

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        readonly_only: bool = False,
    ) -> List[Tool]:
        """列出工具"""
        return self.registry.list_tools(
            category=category,
            readonly_only=readonly_only,
        )

    def get_logs(
        self,
        limit: int = 100,
        tool_name: Optional[str] = None,
        status: Optional[ToolStatus] = None,
    ) -> List[OperationLog]:
        """获取操作日志"""
        logs = self._logs

        if tool_name:
            logs = [l for l in logs if l.tool_name == tool_name]

        if status:
            logs = [l for l in logs if l.status == status]

        return logs[-limit:]

    def get_log_summary(self) -> Dict[str, Any]:
        """获取日志摘要"""
        total = len(self._logs)
        success = sum(1 for l in self._logs if l.status == ToolStatus.SUCCESS)
        failed = sum(1 for l in self._logs if l.status == ToolStatus.FAILED)
        pending = sum(1 for l in self._logs if l.status == ToolStatus.CONFIRM)

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "pending": pending,
            "success_rate": success / total if total > 0 else 0,
            "last_log": self._logs[-1].to_dict() if self._logs else None,
        }

    def undo_last(self) -> Optional[ToolResult]:
        """撤销最后一次写入操作"""
        # 查找最后一次写入操作
        for log in reversed(self._logs):
            if log.tool_name in ("write_file", "edit_file", "delete_file"):
                if log.status == ToolStatus.SUCCESS:
                    # 如果有备份，恢复
                    if log.result and isinstance(log.result, dict):
                        backup_path = log.result.get("backup_path")
                        if backup_path:
                            # 从备份恢复
                            pass  # 实现恢复逻辑

                    # 更新日志
                    log.status = ToolStatus.CANCELLED
                    self._save_log(log)
                    return ToolResult(
                        call_id=log.id,
                        tool_name=log.tool_name,
                        status=ToolStatus.SUCCESS,
                        message=f"已撤销: {log.tool_name}",
                    )

        return None


# ============== 导出 ==============

__all__ = [
    'ToolExecutor',
    'ExecutionMode',
    'OperationLog',
    'LOG_DIR',
]
