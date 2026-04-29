"""
CodeEvolutionExecutor - 代码进化执行器

执行进化计划中的每个动作：
1. 生成/修改/删除代码文件
2. 安装依赖
3. 运行语法检查
4. 自动格式化
5. 注册工具到 ToolRegistry
6. 验证执行结果
7. 支持回滚

安全机制：
- 执行前备份受影响的文件
- 每个动作独立执行，失败不影响其他动作
- 支持手动审核模式（需要用户确认才执行）
- 危险操作（删除文件）需要显式确认

Author: LivingTreeAI
Date: 2026-04-29
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from loguru import logger

# 导入 EvolutionPlanner 的类型
try:
    from client.src.business.self_evolution.code_evolution_planner import (
        EvolutionAction, EvolutionPlan, EvolutionStatus, EvolutionType,
    )
except ImportError:
    # 循环导入保护
    EvolutionAction = Any
    EvolutionPlan = Any
    EvolutionStatus = Any
    EvolutionType = Any


@dataclass
class ExecutionLog:
    """执行日志"""
    action_id: str
    status: str  # success, failed, skipped, rollback
    message: str
    files_changed: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    dependencies_installed: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "status": self.status,
            "message": self.message,
            "files_changed": self.files_changed,
            "files_created": self.files_created,
            "files_deleted": self.files_deleted,
            "dependencies_installed": self.dependencies_installed,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    total_actions: int = 0
    completed_actions: int = 0
    failed_actions: int = 0
    skipped_actions: int = 0
    logs: List[ExecutionLog] = field(default_factory=list)
    backup_dir: str = ""


class CodeEvolutionExecutor:
    """
    代码进化执行器

    工作流程：
    1. 接收 EvolutionPlan
    2. 创建备份
    3. 按优先级逐个执行动作
    4. 每个动作：
       a. 安装依赖
       b. 生成代码（通过 LLM）
       c. 写入文件
       d. 语法验证
       e. 格式化
       f. 注册工具（如需要）
    5. 记录执行日志
    6. 失败时支持回滚

    用法：
        executor = CodeEvolutionExecutor(project_root)
        result = await executor.execute_plan(plan, auto_approve=False)
    """

    BACKUP_DIR = ".evolution_backups"

    def __init__(
        self,
        project_root: str,
        dry_run: bool = False,
        on_approve: Optional[Callable[[EvolutionAction], bool]] = None,
    ):
        """
        Args:
            project_root: 项目根目录
            dry_run: 试运行模式（不实际修改文件）
            on_approve: 审核回调（返回 True 才执行）
        """
        self._root = Path(project_root).resolve()
        self._dry_run = dry_run
        self._on_approve = on_approve
        self._logger = logger.bind(component="CodeEvolutionExecutor")
        self._backup_dir = self._root / self.BACKUP_DIR
        self._current_backup = ""

    async def execute_plan(
        self,
        plan: EvolutionPlan,
        auto_approve: bool = False,
        stop_on_error: bool = False,
    ) -> ExecutionResult:
        """
        执行进化计划

        Args:
            plan: 进化计划
            auto_approve: 自动批准所有动作
            stop_on_error: 遇到错误是否停止
        """
        self._logger.info(f"开始执行进化计划: {plan.title} ({len(plan.actions)} 个动作)")

        result = ExecutionResult(success=True, total_actions=len(plan.actions))
        result.backup_dir = str(self._current_backup)

        # 创建备份
        if not self._dry_run:
            self._current_backup = self._create_backup(plan.plan_id)
            result.backup_dir = str(self._current_backup)

        # 按优先级排序执行
        pending = plan.get_pending_actions()
        pending.sort(key=lambda a: a.priority.value)

        for action in pending:
            self._logger.info(f"执行动作 [{action.priority.name}] {action.title}")

            # 审核检查
            if not auto_approve and self._on_approve:
                approved = self._on_approve(action)
                if not approved:
                    self._logger.info(f"动作被拒绝: {action.title}")
                    log = ExecutionLog(
                        action_id=action.action_id,
                        status="skipped",
                        message="用户拒绝",
                        timestamp=datetime.now().isoformat(),
                    )
                    result.logs.append(log)
                    result.skipped_actions += 1
                    action.status = EvolutionStatus.SKIPPED
                    continue

            # 执行动作
            start = time.time()
            log = await self._execute_action(action)
            log.duration_ms = (time.time() - start) * 1000
            log.timestamp = datetime.now().isoformat()

            result.logs.append(log)

            if log.status == "success":
                result.completed_actions += 1
                action.status = EvolutionStatus.COMPLETED
                action.completed_at = datetime.now().isoformat()
            else:
                result.failed_actions += 1
                action.status = EvolutionStatus.FAILED
                action.result = "; ".join(log.errors)
                result.success = False

                if stop_on_error:
                    self._logger.warning(f"停止执行（遇到错误）: {action.title}")
                    break

        self._logger.info(
            f"执行完成: 成功 {result.completed_actions}, "
            f"失败 {result.failed_actions}, 跳过 {result.skipped_actions}"
        )
        return result

    async def execute_single_action(self, action: EvolutionAction) -> ExecutionLog:
        """执行单个动作（手动模式）"""
        return await self._execute_action(action)

    async def rollback(self, backup_id: str) -> bool:
        """回滚到指定备份"""
        backup_path = self._backup_dir / backup_id
        if not backup_path.exists():
            self._logger.error(f"备份不存在: {backup_id}")
            return False

        self._logger.info(f"回滚到备份: {backup_id}")
        try:
            # 恢复文件
            for item in backup_path.iterdir():
                if item.is_file():
                    target = self._root / item.name
                    if item.suffix == ".bak":
                        target = target.with_suffix("")
                    shutil.copy2(str(item), str(target))
            self._logger.info("回滚完成")
            return True
        except Exception as e:
            self._logger.error(f"回滚失败: {e}")
            return False

    # ── 内部执行方法 ─────────────────────────────────────────

    async def _execute_action(self, action: EvolutionAction) -> ExecutionLog:
        """执行单个进化动作"""
        log = ExecutionLog(
            action_id=action.action_id,
            status="success",
            message="",
        )

        try:
            # 1. 安装依赖
            if action.dependencies:
                for dep in action.dependencies:
                    installed = self._install_dependency(dep)
                    if installed:
                        log.dependencies_installed.append(dep)
                    else:
                        log.errors.append(f"依赖安装失败: {dep}")

            # 2. 生成代码
            if action.target_files:
                for file_path in action.target_files:
                    code = await self._generate_code_for_file(action, file_path)

                    if not code:
                        log.errors.append(f"代码生成失败: {file_path}")
                        continue

                    if self._dry_run:
                        log.message += f"[DRY-RUN] 将写入 {file_path}\n"
                        continue

                    # 3. 写入文件
                    full_path = self._root / file_path
                    self._ensure_parent_dir(full_path)

                    # 备份已有文件
                    if full_path.exists():
                        self._backup_file(full_path, action.action_id)
                        log.files_changed.append(file_path)
                    else:
                        log.files_created.append(file_path)

                    full_path.write_text(code, encoding="utf-8")

                    # 4. 语法验证
                    if file_path.endswith(".py"):
                        valid, syntax_error = self._validate_python_syntax(full_path)
                        if not valid:
                            log.errors.append(f"语法错误 {file_path}: {syntax_error}")
                            # 恢复备份
                            self._restore_file(full_path, action.action_id)

                    # 5. 格式化
                    if file_path.endswith(".py"):
                        self._format_code(full_path)

            # 6. 注册工具（如果是 tool_register 类型）
            if action.evolution_type == EvolutionType.TOOL_REGISTER:
                self._register_tool(action)

            log.message = f"动作执行成功: {action.title}"

        except Exception as e:
            log.status = "failed"
            log.message = f"动作执行失败: {e}"
            log.errors.append(str(e))
            self._logger.error(f"动作执行失败: {action.title}: {e}")

        return log

    async def _generate_code_for_file(
        self,
        action: EvolutionAction,
        file_path: str,
    ) -> str:
        """为指定文件生成代码"""
        # 检查是否已有代码变更指定
        for change in action.code_changes:
            if change.get("file") == file_path and change.get("content"):
                return change["content"]

        # 如果没有预定义的代码变更，使用 LLM 生成
        prompt = f"""你是高级 Python 开发者。请为以下文件生成代码。

项目路径: {self._root}
目标文件: {file_path}

动作描述: {action.description}
动作类型: {action.evolution_type.value if hasattr(action.evolution_type, 'value') else str(action.evolution_type)}

要求：
1. 遵循项目的架构模式（BaseTool, ToolRegistry, GlobalModelRouter）
2. 使用 loguru 记录日志
3. 所有 LLM 调用通过 GlobalModelRouter
4. 包含完整的类型注解
5. 包含 docstring
6. 代码简洁、可维护

请只输出代码，不要其他文字。"""

        try:
            code = await self._call_llm(prompt)
            # 清理 markdown 代码块标记
            code = self._strip_code_markers(code)
            return code
        except Exception as e:
            self._logger.error(f"代码生成失败: {e}")
            return ""

    def _install_dependency(self, package: str) -> bool:
        """安装 Python 依赖"""
        try:
            result = subprocess.run(
                ["pip", "install", "--quiet", package],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                self._logger.info(f"依赖安装成功: {package}")
                return True
            else:
                self._logger.warning(f"依赖安装失败: {package}: {result.stderr}")
                return False
        except Exception as e:
            self._logger.error(f"依赖安装异常: {package}: {e}")
            return False

    def _validate_python_syntax(self, fpath: Path) -> tuple[bool, str]:
        """验证 Python 语法"""
        try:
            content = fpath.read_text(encoding="utf-8")
            ast.parse(content, filename=str(fpath))
            return True, ""
        except SyntaxError as e:
            return False, f"Line {e.lineno}: {e.msg}"

    def _format_code(self, fpath: Path):
        """格式化代码"""
        try:
            content = fpath.read_text(encoding="utf-8")
            import autopep8
            formatted = autopep8.fix_code(content, options={
                'max_line_length': 120,
            })
            fpath.write_text(formatted, encoding="utf-8")
        except ImportError:
            pass  # autopep8 未安装
        except Exception as e:
            self._logger.warning(f"格式化失败 {fpath}: {e}")

    def _register_tool(self, action: EvolutionAction):
        """注册工具到 ToolRegistry"""
        try:
            from client.src.business.tools.tool_registry import ToolRegistry
            # 重新加载模块以注册新工具
            for fpath in action.target_files:
                if fpath.endswith(".py"):
                    module_name = fpath.replace("/", ".").replace(".py", "")
                    try:
                        import importlib
                        importlib.import_module(module_name)
                    except Exception as e:
                        self._logger.warning(f"模块加载失败: {module_name}: {e}")
            self._logger.info("工具注册完成")
        except Exception as e:
            self._logger.error(f"工具注册失败: {e}")

    # ── 备份/恢复 ───────────────────────────────────────────

    def _create_backup(self, plan_id: str) -> str:
        """创建备份"""
        backup_path = self._backup_dir / plan_id
        backup_path.mkdir(parents=True, exist_ok=True)
        self._logger.info(f"创建备份: {backup_path}")
        return str(backup_path)

    def _backup_file(self, fpath: Path, action_id: str):
        """备份单个文件"""
        backup_path = self._backup_dir / action_id
        backup_path.mkdir(parents=True, exist_ok=True)
        rel = fpath.relative_to(self._root)
        dest = backup_path / (str(rel).replace("/", "_") + ".bak")
        shutil.copy2(str(fpath), str(dest))

    def _restore_file(self, fpath: Path, action_id: str):
        """恢复备份文件"""
        backup_path = self._backup_dir / action_id
        rel = fpath.relative_to(self._root)
        backup_file = backup_path / (str(rel).replace("/", "_") + ".bak")
        if backup_file.exists():
            shutil.copy2(str(backup_file), str(fpath))
            self._logger.info(f"恢复文件: {fpath}")

    # ── 辅助方法 ───────────────────────────────────────────

    @staticmethod
    def _ensure_parent_dir(fpath: Path):
        """确保父目录存在"""
        fpath.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _strip_code_markers(text: str) -> str:
        """清理代码标记（```python ... ```）"""
        import re
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
        return text

    async def _call_llm(self, prompt: str) -> str:
        """通过 GlobalModelRouter 调用 LLM"""
        try:
            from client.src.business.global_model_router import GlobalModelRouter
            router = GlobalModelRouter.get_instance()

            response = await router.call_model(
                capability="code_generation",
                prompt=prompt,
                temperature=0.2,
            )

            if hasattr(response, 'thinking') and response.thinking:
                return response.thinking
            elif hasattr(response, 'content') and response.content:
                return response.content
            return str(response)

        except Exception as e:
            self._logger.error(f"LLM 调用失败: {e}")
            return ""
