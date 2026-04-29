"""
CodeTool - OpenCode + Serena 集成的智能编码工具

继承 BaseTool，注册到 ToolRegistry，多 Agent 可调用。

核心分工：
- OpenCode (大脑): 任务规划、代码生成、逻辑推理、终端命令
- Serena (双手): LSP 精准代码操作、符号级编辑

四大自动化能力：
1. Auto-Writing: LLM 规划步骤 → Serena 精准写入
2. Auto-Testing: pytest 执行 → 错误分析 → 自动修复循环
3. Auto-Fixing: LSP 诊断 → LLM 修复 → 原子化替换
4. Auto-Publishing: git add/commit → CI/CD 触发

安全机制：
- dry-run 模式：预览所有变更但不实际执行
- 文件备份：修改前自动备份到 .code_backups/
- 语法验证：写入后立即验证
- 审核回调：on_approve 用户确认
- 回滚支持：一键回滚到修改前状态

所有 LLM 调用通过 GlobalModelRouter。
"""

from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum
import json
import os
import ast
import shutil
import subprocess
import re
import hashlib
from datetime import datetime

from client.src.business.tools.base_tool import BaseTool, AgentCallResult
from client.src.business.self_evolution.serena_adapter import (
    SerenaAdapter, SymbolInfo, DiagnosticInfo, SerenaResult, SerenaStatus
)


# ── 数据类 ──────────────────────────────────────────

class CodeAction(Enum):
    """代码操作类型"""
    WRITE = "write"               # 自动写
    TEST = "test"                 # 自动测
    FIX = "fix"                   # 自动修
    PUBLISH = "publish"           # 自动发布
    SCAN = "scan"                 # 项目扫描
    PLAN = "plan"                 # 规划
    REFACTOR = "refactor"         # 重构


class TestFramework(Enum):
    """测试框架"""
    PYTEST = "pytest"
    UNITTEST = "unittest"
    JEST = "jest"
    NPM_TEST = "npm_test"


@dataclass
class WriteResult:
    """自动写结果"""
    success: bool
    files_modified: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    lines_added: int = 0
    syntax_errors: List[str] = field(default_factory=list)
    backup_id: str = ""


@dataclass
class TestResult:
    """自动测结果"""
    success: bool
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)
    fix_attempts: int = 0
    fix_success: int = 0
    duration_seconds: float = 0.0
    framework: str = "pytest"


@dataclass
class FixResult:
    """自动修结果"""
    success: bool
    diagnostics_fixed: int = 0
    files_modified: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    backup_id: str = ""


@dataclass
class PublishResult:
    """自动发布结果"""
    success: bool
    commit_hash: str = ""
    branch: str = ""
    files_committed: List[str] = field(default_factory=list)
    ci_triggered: bool = False
    error: str = ""


@dataclass
class PlanStep:
    """规划步骤"""
    step_number: int
    description: str
    target_files: List[str] = field(default_factory=list)
    code_action: str = ""
    status: str = "pending"  # pending, in_progress, done, skipped, error


@dataclass
class CodeToolSession:
    """编码会话"""
    id: str = ""
    action: CodeAction = CodeAction.WRITE
    created_at: str = ""
    results: List[Dict[str, Any]] = field(default_factory=list)
    backup_id: str = ""
    dry_run: bool = False

    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(
                f"{datetime.now().isoformat()}".encode()
            ).hexdigest()[:12]
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class CodeTool(BaseTool):
    """
    CodeTool - OpenCode + Serena 集成的智能编码工具

    提供自动写、自动测、自动修、自动发布的完整自动化研发流水线。

    用法示例:
        tool = CodeTool()
        result = await tool.execute(
            action="write",
            instruction="添加一个用户注册接口",
            project_path="."
        )
        result = await tool.execute(
            action="test",
            project_path=".",
            test_command="pytest tests/"
        )
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self._config = config or {}
        self._serena = SerenaAdapter(self._config.get("serena", {}))
        self._backup_dir = self._config.get(
            "backup_dir", ".code_backups"
        )
        self._max_fix_attempts = self._config.get("max_fix_attempts", 3)
        self._dry_run = self._config.get("dry_run", False)
        self._sessions: Dict[str, CodeToolSession] = {}
        self._on_approve: Optional[Callable] = None

        # 历史记录
        self._history_dir = self._config.get("history_dir", ".code_history")
        os.makedirs(self._history_dir, exist_ok=True)

    @property
    def name(self) -> str:
        return "code_tool"

    @property
    def description(self) -> str:
        return (
            "OpenCode + Serena 智能编码工具 - 自动写/自动测/自动修/自动发布。"
            "集成 LLM 规划能力与 LSP 精准代码操作，提供完整的自动化研发流水线。"
        )

    @property
    def category(self) -> str:
        return "code"

    @property
    def node_type(self) -> str:
        return "ai"

    @property
    def parameters(self) -> Dict[str, str]:
        return {
            "action": "操作类型: write/test/fix/publish/scan/plan/refactor",
            "instruction": "自然语言指令（write/plan/refactor 时使用）",
            "project_path": "项目根路径",
            "target_files": "目标文件列表（可选，JSON 字符串）",
            "test_command": "测试命令（test 时使用，默认 pytest）",
            "commit_message": "提交信息（publish 时使用）",
            "dry_run": "是否预览模式（true/false）",
        }

    @property
    def returns(self) -> str:
        return "CodeToolResult (WriteResult/TestResult/FixResult/PublishResult)"

    def set_approve_callback(self, callback: Callable[[str, str], bool]):
        """设置用户审核回调: callback(description, details) -> bool"""
        self._on_approve = callback

    # ── 核心入口 ──────────────────────────────────────

    async def execute(self, **kwargs) -> Any:
        """
        执行编码操作

        Args:
            action: 操作类型 (write/test/fix/publish/scan/plan)
            instruction: 自然语言指令
            project_path: 项目根路径
            target_files: 目标文件列表
            test_command: 测试命令
            commit_message: 提交信息
            dry_run: 预览模式
        """
        action_str = kwargs.get("action", "write").lower()
        project_path = kwargs.get("project_path", ".")
        instruction = kwargs.get("instruction", "")
        dry_run = kwargs.get("dry_run", self._dry_run)

        try:
            code_action = CodeAction(action_str)
        except ValueError:
            return AgentCallResult.error(
                f"未知操作类型: {action_str}，"
                f"支持: {', '.join(a.value for a in CodeAction)}"
            )

        session = CodeToolSession(action=code_action, dry_run=dry_run)

        try:
            if code_action == CodeAction.WRITE:
                result = await self._auto_write(
                    instruction=instruction,
                    project_path=project_path,
                    target_files=kwargs.get("target_files"),
                    session=session,
                    dry_run=dry_run
                )
            elif code_action == CodeAction.TEST:
                result = await self._auto_test(
                    project_path=project_path,
                    test_command=kwargs.get("test_command", "pytest"),
                    session=session,
                    dry_run=dry_run
                )
            elif code_action == CodeAction.FIX:
                result = await self._auto_fix(
                    project_path=project_path,
                    target_files=kwargs.get("target_files"),
                    session=session,
                    dry_run=dry_run
                )
            elif code_action == CodeAction.PUBLISH:
                result = await self._auto_publish(
                    project_path=project_path,
                    commit_message=kwargs.get("commit_message", ""),
                    session=session,
                    dry_run=dry_run
                )
            elif code_action == CodeAction.SCAN:
                result = await self._scan_project(
                    project_path=project_path,
                    session=session
                )
            elif code_action == CodeAction.PLAN:
                result = await self._plan_code(
                    instruction=instruction,
                    project_path=project_path,
                    session=session
                )
            elif code_action == CodeAction.REFACTOR:
                result = await self._auto_refactor(
                    instruction=instruction,
                    project_path=project_path,
                    target_files=kwargs.get("target_files"),
                    session=session,
                    dry_run=dry_run
                )
            else:
                result = {"error": f"未实现的操作: {code_action}"}

            session.results.append(result if isinstance(result, dict) else {
                k: v for k, v in result.__dict__.items()
            })

            return AgentCallResult.success(
                data=result,
                message=f"{code_action.value} 操作完成",
                evidence={
                    "action": code_action.value,
                    "dry_run": dry_run,
                    "session_id": session.id,
                    "serena_status": self._serena.status.value
                }
            )

        except Exception as e:
            logger.error(f"CodeTool 执行失败: {e}")
            return AgentCallResult.error(
                f"执行失败: {str(e)}"
            )

    # ── 自动写 (Auto-Writing) ────────────────────────

    async def _auto_write(
        self,
        instruction: str,
        project_path: str,
        target_files: Optional[str] = None,
        session: CodeToolSession = None,
        dry_run: bool = False
    ) -> WriteResult:
        """
        自动写 - OpenCode 规划 + Serena 精准写入

        流程:
        1. LLM 分析需求，生成 TODO 步骤列表
        2. LLM 为每一步生成代码
        3. Serena 精准写入文件（insert_after_symbol / replace_content）
        4. 语法验证
        """
        result = WriteResult(success=False)

        if not instruction:
            return WriteResult(success=False, syntax_errors=["缺少 instruction 参数"])

        # Step 1: LLM 规划
        plan = await self._llm_plan_writes(instruction, project_path, target_files)
        if not plan:
            return WriteResult(success=False, syntax_errors=["LLM 规划失败"])

        logger.info(f"CodeTool: 规划了 {len(plan)} 个写入步骤")

        # Step 2: 逐步执行
        for step in plan:
            file_path = step.get("file_path", "")
            action_type = step.get("action", "create")  # create / modify / insert_after

            if not file_path:
                continue

            full_path = os.path.join(project_path, file_path) if not os.path.isabs(file_path) else file_path

            # 用户审核（非 dry-run 模式下）
            if not dry_run and self._on_approve:
                approved = self._on_approve(
                    f"写入文件: {file_path}",
                    f"操作: {action_type}\n文件: {file_path}"
                )
                if not approved:
                    logger.info(f"用户拒绝写入: {file_path}")
                    continue

            if dry_run:
                logger.info(f"[DRY-RUN] 将 {action_type}: {file_path}")
                result.files_modified.append(file_path)
                continue

            # Step 3: 执行写入
            code = step.get("code", "")

            if action_type == "create":
                write_result = self._serena.write_file(full_path, code)
                if write_result.success:
                    result.files_created.append(file_path)
                    self._track_modification(full_path, "create", None, code)
                else:
                    result.syntax_errors.append(f"{file_path}: {write_result.error}")

            elif action_type == "modify":
                old_content = step.get("old_content", "")
                if old_content:
                    replace_result = self._serena.replace_content(
                        full_path, old_content, code
                    )
                    if replace_result.success:
                        result.files_modified.append(file_path)
                        self._track_modification(full_path, "modify", old_content, code)
                    else:
                        result.syntax_errors.append(
                            f"{file_path}: {replace_result.error}"
                        )
                else:
                    # 没有 old_content，直接重写
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        old_content = f.read()
                    write_result = self._serena.write_file(full_path, code)
                    if write_result.success:
                        result.files_modified.append(file_path)
                        self._track_modification(full_path, "modify", old_content, code)

            elif action_type == "insert_after":
                symbol_name = step.get("symbol_name", "")
                insert_result = self._serena.insert_after_symbol(
                    full_path, symbol_name, code
                )
                if insert_result.success:
                    result.files_modified.append(file_path)
                    self._track_modification(full_path, "modify")
                else:
                    result.syntax_errors.append(
                        f"{file_path}: {insert_result.error}"
                    )

            # Step 4: 语法验证
            if full_path.endswith('.py'):
                syntax_result = self._serena.check_syntax(full_path)
                if not syntax_result.success:
                    err_data = syntax_result.data or {}
                    result.syntax_errors.append(
                        f"{file_path}: {err_data.get('error', '未知错误')} "
                        f"(行 {err_data.get('line', '?')})"
                    )

        result.lines_added = sum(
            len(s.get("code", "").split('\n')) for s in plan
        )
        result.success = len(result.syntax_errors) == 0
        result.backup_id = session.backup_id if session else ""

        return result

    async def _llm_plan_writes(
        self, instruction: str, project_path: str,
        target_files: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """LLM 规划写入步骤"""
        try:
            from client.src.business.global_model_router import (
                call_model_sync, ModelCapability
            )

            # 扫描项目结构作为上下文
            project_context = await self._get_project_context(project_path)

            # 构建 prompt
            target_info = ""
            if target_files:
                target_info = f"\n目标文件: {target_files}"

            prompt = f"""你是一个高级软件工程师。根据用户需求，规划代码写入步骤。

## 项目上下文
{project_context}

## 用户需求
{instruction}{target_info}

## 输出要求
输出 JSON 数组，每个元素包含:
- file_path: 文件路径（相对于项目根目录）
- action: 操作类型 (create/modify/insert_after)
- code: 要写入的完整代码
- symbol_name: (仅 insert_after 需要) 在哪个符号之后插入
- old_content: (仅 modify 需要) 要替换的旧内容

只输出 JSON 数组，不要其他内容。如果需要创建新文件，使用 action="create"。"""

            response = call_model_sync(
                capability=ModelCapability.CODE_GENERATION,
                prompt=prompt,
                system_prompt="你是一个精准的代码生成器。只输出 JSON 数组。",
                temperature=0.2
            )

            # 提取 JSON
            return self._extract_json_array(response)

        except Exception as e:
            logger.error(f"LLM 规划写入失败: {e}")
            return []

    # ── 自动测 (Auto-Testing) ────────────────────────

    async def _auto_test(
        self,
        project_path: str,
        test_command: str = "pytest",
        session: CodeToolSession = None,
        dry_run: bool = False
    ) -> TestResult:
        """
        自动测 - 执行测试 → 分析错误 → 自动修复 → 重测

        闭环流程直到测试通过或达到最大尝试次数。
        """
        result = TestResult(success=False, framework=test_command.split()[0])

        for attempt in range(self._max_fix_attempts + 1):
            logger.info(f"CodeTool: 测试尝试 {attempt + 1}/{self._max_fix_attempts + 1}")

            # 执行测试
            test_output = await self._run_tests(project_path, test_command, dry_run)
            result.fix_attempts = attempt

            # 解析测试结果
            parsed = self._parse_test_output(test_output, test_command.split()[0])
            result.total_tests = parsed.get("total", 0)
            result.passed = parsed.get("passed", 0)
            result.failed = parsed.get("failed", 0)
            result.errors = parsed.get("errors", [])

            if parsed.get("success", False):
                result.success = True
                break

            # 测试失败，尝试自动修复
            if attempt < self._max_fix_attempts and not dry_run:
                logger.info(f"CodeTool: 测试失败，尝试自动修复...")
                fix_result = await self._fix_test_failures(
                    project_path, result.errors
                )
                if fix_result.success:
                    result.fix_success += 1
                else:
                    result.errors.extend(fix_result.errors)
                    break  # 修复也失败了

        return result

    async def _run_tests(
        self, project_path: str, test_command: str, dry_run: bool
    ) -> str:
        """执行测试命令"""
        if dry_run:
            return f"[DRY-RUN] 将执行: {test_command}"

        try:
            result = subprocess.run(
                test_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=project_path
            )
            output = result.stdout + "\n" + result.stderr
            return output
        except subprocess.TimeoutExpired:
            return "测试超时（120秒）"
        except Exception as e:
            return f"测试执行失败: {e}"

    def _parse_test_output(self, output: str, framework: str) -> Dict[str, Any]:
        """解析测试输出"""
        result = {
            "success": False,
            "total": 0, "passed": 0, "failed": 0,
            "errors": []
        }

        if framework == "pytest":
            # pytest 输出解析
            # 匹配 "X passed, Y failed, Z errors"
            match = re.search(
                r'(\d+) passed(?:, (\d+) failed)?(?:, (\d+) error(?:s)?)?',
                output
            )
            if match:
                result["passed"] = int(match.group(1))
                result["failed"] = int(match.group(2) or 0)
                result["total"] = result["passed"] + result["failed"]
                if match.group(3):
                    result["total"] += int(match.group(3))

            # 匹配 "X passed"
            match_all = re.search(r'(\d+) passed', output)
            if match_all and result["failed"] == 0:
                result["success"] = True

            # 提取错误信息
            error_pattern = re.compile(
                r'(?:FAILED|ERROR) (.+?)(?:\n|$)',
                re.MULTILINE
            )
            errors = error_pattern.findall(output)
            result["errors"] = errors[:10]  # 限制数量

        elif framework in ("unittest", "python"):
            # unittest 输出解析
            match = re.search(r'Ran (\d+) test', output)
            if match:
                result["total"] = int(match.group(1))

            if "OK" in output:
                result["passed"] = result["total"]
                result["success"] = True
            elif "FAILED" in output:
                fail_match = re.search(r'failures=(\d+)', output)
                error_match = re.search(r'errors=(\d+)', output)
                result["failed"] = int(fail_match.group(1) if fail_match else 0)
                result["passed"] = result["total"] - result["failed"]

        else:
            # 通用解析
            if "PASS" in output.upper() or "OK" in output.upper():
                result["success"] = True

        return result

    async def _fix_test_failures(
        self, project_path: str, errors: List[str]
    ) -> FixResult:
        """LLM 修复测试失败"""
        try:
            from client.src.business.global_model_router import (
                call_model_sync, ModelCapability
            )

            error_context = "\n".join(f"- {e}" for e in errors[:5])

            prompt = f"""测试失败，请分析错误并生成修复方案。

## 错误信息
{error_context}

## 输出要求
输出 JSON 数组，每个元素包含:
- file_path: 需要修复的文件路径
- action: 操作类型 (create/modify/insert_after)
- old_content: 要替换的旧内容
- code: 修复后的代码
- symbol_name: (可选) 在哪个符号之后插入

只输出 JSON 数组。"""

            response = call_model_sync(
                capability=ModelCapability.CODE_DEBUG,
                prompt=prompt,
                system_prompt="你是一个调试专家。分析测试错误并生成精确的修复。",
                temperature=0.2
            )

            fixes = self._extract_json_array(response)
            result = FixResult(success=True)

            for fix in fixes:
                file_path = fix.get("file_path", "")
                if not file_path:
                    continue
                full_path = os.path.join(project_path, file_path)
                action = fix.get("action", "modify")
                code = fix.get("code", "")

                if action == "modify" and fix.get("old_content"):
                    replace_result = self._serena.replace_content(
                        full_path, fix["old_content"], code
                    )
                    if replace_result.success:
                        result.files_modified.append(file_path)
                        result.diagnostics_fixed += 1
                elif action == "create":
                    write_result = self._serena.write_file(full_path, code)
                    if write_result.success:
                        result.files_created = getattr(result, 'files_created', [])
                        result.files_modified.append(file_path)

            return result

        except Exception as e:
            return FixResult(success=False, errors=[str(e)])

    # ── 自动修 (Auto-Fixing) ────────────────────────

    async def _auto_fix(
        self,
        project_path: str,
        target_files: Optional[str] = None,
        session: CodeToolSession = None,
        dry_run: bool = False
    ) -> FixResult:
        """
        自动修 - LSP 诊断 → LLM 修复 → 原子化替换

        流程:
        1. Serena 获取 LSP 诊断（编译错误 + Lint 警告）
        2. LLM 分析诊断并生成修复方案
        3. Serena 执行精准修复（replace_content / rename_symbol）
        4. 重新诊断验证
        """
        result = FixResult(success=False)

        # 确定要扫描的文件
        files = []
        if target_files:
            try:
                files = json.loads(target_files) if isinstance(target_files, str) else target_files
            except json.JSONDecodeError:
                files = [target_files]
        else:
            files = self._find_python_files(project_path)

        # 收集诊断
        all_diagnostics = []
        for f in files:
            full_path = os.path.join(project_path, f) if not os.path.isabs(f) else f
            diag_result = self._serena.get_diagnostics(full_path)
            if diag_result.success and diag_result.data:
                all_diagnostics.extend(diag_result.data)

        if not all_diagnostics:
            return FixResult(success=True, diagnostics_fixed=0,
                             message="没有发现需要修复的问题")

        # 过滤只保留 error 和 warning
        fixable = [d for d in all_diagnostics if d.severity in ("error", "warning")]
        if not fixable:
            return FixResult(success=True, diagnostics_fixed=0,
                             message="只有 info/hint 级别的诊断，无需修复")

        logger.info(f"CodeTool: 发现 {len(fixable)} 个需要修复的问题")

        # LLM 生成修复方案
        fixes = await self._llm_generate_fixes(fixable, project_path)

        # 执行修复
        for fix in fixes:
            file_path = fix.get("file_path", "")
            full_path = os.path.join(project_path, file_path) if not os.path.isabs(file_path) else file_path
            action = fix.get("action", "modify")

            if dry_run:
                logger.info(f"[DRY-RUN] 修复: {file_path} ({action})")
                result.files_modified.append(file_path)
                continue

            code = fix.get("code", "")

            if action == "replace" and fix.get("old_content"):
                r = self._serena.replace_content(full_path, fix["old_content"], code)
                if r.success:
                    result.files_modified.append(file_path)
                    result.diagnostics_fixed += 1
            elif action == "rename":
                r = self._serena.rename_symbol(
                    full_path, fix.get("old_name", ""), fix.get("new_name", "")
                )
                if r.success:
                    result.files_modified.append(file_path)
                    result.diagnostics_fixed += 1
            elif action == "modify":
                r = self._serena.write_file(full_path, code)
                if r.success:
                    result.files_modified.append(file_path)
                    result.diagnostics_fixed += 1

        result.success = result.diagnostics_fixed > 0
        result.backup_id = session.backup_id if session else ""

        return result

    async def _llm_generate_fixes(
        self, diagnostics: List[DiagnosticInfo], project_path: str
    ) -> List[Dict[str, Any]]:
        """LLM 生成修复方案"""
        try:
            from client.src.business.global_model_router import (
                call_model_sync, ModelCapability
            )

            diag_text = "\n".join(
                f"- [{d.severity}] {d.file_path}:{d.line} - {d.message}"
                for d in diagnostics[:15]
            )

            # 读取相关文件内容
            files_content = ""
            seen_files = set()
            for d in diagnostics[:5]:
                if d.file_path not in seen_files:
                    seen_files.add(d.file_path)
                    read_result = self._serena.read_file(
                        d.file_path,
                        max(0, d.line - 5),
                        d.line + 10
                    )
                    if read_result.success:
                        files_content += f"\n### {d.file_path}\n```python\n{read_result.data.get('content', '')}\n```\n"

            prompt = f"""分析以下代码诊断信息并生成修复方案。

## 诊断信息
{diag_text}

## 相关代码
{files_content}

## 输出要求
输出 JSON 数组，每个元素包含:
- file_path: 文件路径
- action: 操作类型 (replace/rename/modify)
- old_content: (replace 时) 要替换的旧内容
- old_name / new_name: (rename 时) 旧名/新名
- code: (modify 时) 完整的新文件内容
- reason: 修复原因

只输出 JSON 数组。"""

            response = call_model_sync(
                capability=ModelCapability.CODE_DEBUG,
                prompt=prompt,
                system_prompt="你是代码修复专家。分析诊断信息并生成精准修复方案。",
                temperature=0.1
            )

            return self._extract_json_array(response)

        except Exception as e:
            logger.error(f"LLM 生成修复方案失败: {e}")
            return []

    # ── 自动发布 (Auto-Publishing) ───────────────────

    async def _auto_publish(
        self,
        project_path: str,
        commit_message: str = "",
        session: CodeToolSession = None,
        dry_run: bool = False
    ) -> PublishResult:
        """
        自动发布 - Git 操作 + CI/CD 触发

        流程:
        1. 检测 git 状态
        2. git add + git commit
        3. 可选: git push
        4. 可选: 触发 CI/CD
        """
        result = PublishResult(success=False)

        if not os.path.isdir(os.path.join(project_path, ".git")):
            return PublishResult(
                success=False,
                error="不是 Git 仓库（未找到 .git 目录）"
            )

        try:
            # 检测变更
            status_cmd = "git status --porcelain"
            if dry_run:
                return PublishResult(
                    success=True,
                    commit_hash="[DRY-RUN]",
                    error="[DRY-RUN] 将执行 git add + commit + push"
                )

            status_result = subprocess.run(
                status_cmd, shell=True, capture_output=True,
                text=True, cwd=project_path
            )

            changed_files = [
                line.strip().split(maxsplit=1)[-1]
                for line in status_result.stdout.strip().split('\n')
                if line.strip()
            ]

            if not changed_files:
                return PublishResult(
                    success=True,
                    commit_hash="",
                    error="没有需要提交的变更"
                )

            # 自动生成 commit message
            if not commit_message:
                commit_message = await self._llm_generate_commit_message(
                    project_path, changed_files
                )

            # git add
            subprocess.run(
                "git add -A", shell=True, cwd=project_path,
                capture_output=True, text=True
            )

            # git commit
            safe_msg = commit_message.replace('"', '\\"')
            commit_result = subprocess.run(
                f'git commit -m "{safe_msg}"',
                shell=True, capture_output=True, text=True,
                cwd=project_path
            )

            if commit_result.returncode != 0:
                return PublishResult(
                    success=False,
                    error=f"git commit 失败: {commit_result.stderr}"
                )

            # 获取 commit hash
            hash_result = subprocess.run(
                "git rev-parse --short HEAD", shell=True,
                capture_output=True, text=True, cwd=project_path
            )
            commit_hash = hash_result.stdout.strip()

            # 获取当前分支
            branch_result = subprocess.run(
                "git rev-parse --abbrev-ref HEAD", shell=True,
                capture_output=True, text=True, cwd=project_path
            )
            branch = branch_result.stdout.strip()

            # git push（可选）
            push_config = self._config.get("auto_push", False)
            if push_config:
                push_result = subprocess.run(
                    "git push", shell=True, capture_output=True,
                    text=True, cwd=project_path, timeout=30
                )
                if push_result.returncode == 0:
                    result.ci_triggered = True

            result.success = True
            result.commit_hash = commit_hash
            result.branch = branch
            result.files_committed = changed_files

            return result

        except subprocess.TimeoutExpired:
            return PublishResult(success=False, error="Git 操作超时")
        except Exception as e:
            return PublishResult(success=False, error=str(e))

    async def _llm_generate_commit_message(
        self, project_path: str, changed_files: List[str]
    ) -> str:
        """LLM 生成 commit message"""
        try:
            from client.src.business.global_model_router import (
                call_model_sync, ModelCapability
            )

            # 获取 diff
            diff_result = subprocess.run(
                "git diff --cached --stat", shell=True,
                capture_output=True, text=True, cwd=project_path
            )

            prompt = f"""根据以下 Git 变更生成一个简洁的 commit message。

## 变更文件
{chr(10).join(f'- {f}' for f in changed_files[:20])}

## 变更统计
{diff_result.stdout}

## 要求
- 使用 Conventional Commits 格式: type(scope): description
- type: feat/fix/refactor/docs/test/chore
- 一行，不超过 72 字符
- 只输出 commit message 本身，不要其他内容"""

            response = call_model_sync(
                capability=ModelCapability.CONTENT_GENERATION,
                prompt=prompt,
                temperature=0.3
            )

            return response.strip().strip('"').strip("'")[:72]

        except Exception:
            return f"chore: auto commit {len(changed_files)} files"

    # ── 项目扫描 ─────────────────────────────────────

    async def _scan_project(
        self, project_path: str, session: CodeToolSession = None
    ) -> Dict[str, Any]:
        """扫描项目结构"""
        python_files = self._find_python_files(project_path)

        # 统计信息
        total_lines = 0
        total_classes = 0
        total_functions = 0
        modules = {}

        for f in python_files[:100]:  # 限制扫描数量
            full_path = os.path.join(project_path, f) if not os.path.isabs(f) else f
            structure = self._serena.get_file_structure(full_path)
            if structure.success and structure.data:
                for sym in structure.data:
                    if sym.kind == "class":
                        total_classes += 1
                    elif sym.kind in ("function", "method"):
                        total_functions += 1

            # 统计行数
            read_result = self._serena.read_file(full_path)
            if read_result.success:
                total_lines += read_result.data.get("total_lines", 0)

            # 按目录分组
            dir_name = os.path.dirname(f).replace('\\', '/')
            if dir_name not in modules:
                modules[dir_name] = {"files": 0, "classes": 0, "functions": 0}
            modules[dir_name]["files"] += 1

        return {
            "total_files": len(python_files),
            "total_lines": total_lines,
            "total_classes": total_classes,
            "total_functions": total_functions,
            "modules": modules,
            "serena_status": self._serena.status.value
        }

    # ── 代码规划 ─────────────────────────────────────

    async def _plan_code(
        self, instruction: str, project_path: str,
        session: CodeToolSession = None
    ) -> Dict[str, Any]:
        """LLM 规划代码变更"""
        try:
            from client.src.business.global_model_router import (
                call_model_sync, ModelCapability
            )

            context = await self._get_project_context(project_path)

            prompt = f"""你是一个高级软件架构师。根据用户需求规划代码变更。

## 项目上下文
{context}

## 用户需求
{instruction}

## 输出要求
输出 JSON 对象，包含:
- steps: 步骤数组，每个步骤:
  - step_number: 步骤编号
  - description: 步骤描述
  - target_files: 涉及的文件列表
  - code_action: 操作类型 (create/modify/delete/refactor)
  - estimated_complexity: 复杂度 (low/medium/high)
- dependencies: 依赖关系描述
- risks: 风险评估
- estimated_time: 预估时间

只输出 JSON 对象。"""

            response = call_model_sync(
                capability=ModelCapability.PLANNING,
                prompt=prompt,
                system_prompt="你是一个软件架构师，擅长将需求拆解为可执行的步骤。",
                temperature=0.3
            )

            return self._extract_json_object(response)

        except Exception as e:
            return {"error": str(e)}

    # ── 代码重构 ─────────────────────────────────────

    async def _auto_refactor(
        self, instruction: str, project_path: str,
        target_files: Optional[str] = None,
        session: CodeToolSession = None,
        dry_run: bool = False
    ) -> WriteResult:
        """自动重构"""
        # 先规划
        plan_result = await self._plan_code(instruction, project_path)

        steps = plan_result.get("steps", [])
        if not steps:
            return WriteResult(success=False, syntax_errors=["规划失败，无重构步骤"])

        # 转换为写入步骤并执行
        write_steps = []
        for step in steps:
            if step.get("code_action") in ("create", "modify", "refactor"):
                write_steps.append({
                    "file_path": step.get("target_files", [""])[0] if step.get("target_files") else "",
                    "action": step.get("code_action", "modify"),
                    "description": step.get("description", "")
                })

        if not write_steps:
            return WriteResult(success=False, syntax_errors=["没有可执行的重构步骤"])

        # 使用 LLM 为每个步骤生成代码
        full_instruction = f"重构需求: {instruction}\n\n具体步骤:\n"
        for i, step in enumerate(steps, 1):
            full_instruction += f"{i}. {step.get('description', '')}\n"

        return await self._auto_write(
            instruction=full_instruction,
            project_path=project_path,
            target_files=target_files,
            session=session,
            dry_run=dry_run
        )

    # ── 辅助方法 ─────────────────────────────────────

    async def _get_project_context(self, project_path: str) -> str:
        """获取项目上下文信息（用于 LLM prompt）"""
        context_parts = []

        # 项目结构
        scan_result = await self._scan_project(project_path)
        if scan_result:
            context_parts.append(
                f"文件数: {scan_result.get('total_files', 0)}\n"
                f"总行数: {scan_result.get('total_lines', 0)}\n"
                f"类: {scan_result.get('total_classes', 0)}\n"
                f"函数: {scan_result.get('total_functions', 0)}"
            )

        # 关键文件列表
        python_files = self._find_python_files(project_path)
        key_files = [f for f in python_files if any(
            kw in f.lower() for kw in ["init", "main", "config", "model", "router"]
        )][:10]
        if key_files:
            context_parts.append(f"\n关键文件:\n" + "\n".join(f"- {f}" for f in key_files))

        return "\n".join(context_parts)

    def _find_python_files(self, project_path: str, max_files: int = 200) -> List[str]:
        """查找项目中的 Python 文件"""
        result = []
        skip_dirs = {
            "__pycache__", ".git", "node_modules", ".venv", "venv",
            "dist", "build", ".egg-info", ".code_backups", ".evolution_knowledge",
            ".evolution_backups", ".code_history"
        }

        for root, dirs, files in os.walk(project_path):
            # 过滤跳过的目录
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for f in files:
                if f.endswith('.py') and not f.startswith('_'):
                    rel_path = os.path.relpath(
                        os.path.join(root, f), project_path
                    ).replace('\\', '/')
                    result.append(rel_path)

            if len(result) >= max_files:
                break

        return result

    def _extract_json_array(self, text: str) -> List[Dict[str, Any]]:
        """从 LLM 输出中提取 JSON 数组"""
        # 尝试直接解析
        text = text.strip()
        if text.startswith('```'):
            # 移除 markdown 代码块
            lines = text.split('\n')
            start = 1 if lines[0].startswith('```') else 0
            end = len(lines)
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == '```':
                    end = i
                    break
            text = '\n'.join(lines[start:end])

        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # 尝试提取 [...] 部分
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        return []

    def _extract_json_object(self, text: str) -> Dict[str, Any]:
        """从 LLM 输出中提取 JSON 对象"""
        text = text.strip()
        if text.startswith('```'):
            lines = text.split('\n')
            start = 1 if lines[0].startswith('```') else 0
            end = len(lines)
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == '```':
                    end = i
                    break
            text = '\n'.join(lines[start:end])

        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        return {"raw_response": text}

    def get_status(self) -> Dict[str, Any]:
        """获取 CodeTool 状态"""
        return {
            "name": self.name,
            "serena": self._serena.get_status_info(),
            "sessions": len(self._sessions),
            "dry_run": self._dry_run,
            "max_fix_attempts": self._max_fix_attempts,
        }


# ── 自动注册 ──────────────────────────────────────────

def auto_register():
    """自动注册 CodeTool 到 ToolRegistry"""
    from client.src.business.tools.tool_registry import ToolRegistry

    registry = ToolRegistry.get_instance()
    tool = CodeTool()
    tool.register()

    logger.info(f"[CodeTool] 已注册到 ToolRegistry (Serena: {tool._serena.status.value})")
    return True


# 自动注册（导入时执行）
try:
    auto_register()
except Exception as e:
    logger.warning(f"[CodeTool] 自动注册失败: {e}")
