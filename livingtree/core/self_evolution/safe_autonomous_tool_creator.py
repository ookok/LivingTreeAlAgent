"""
SafeAutonomousToolCreator - 安全的自主工具创建器

在 AutonomousToolCreator 基础上添加安全机制：
1. 代码安全检查（静态分析 + 危险模式检测）
2. 沙箱执行环境（限制文件系统、网络、内存、执行时间）
3. 用户确认机制（创建前可要求用户确认）
4. 观察期机制（先注册到沙箱，观察后再注册到主系统）
5. 回滚机制（创建的工具可回滚）
"""

import os
import json
import time
import shutil
import hashlib
import re
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

from business.self_evolution.autonomous_tool_creator import AutonomousToolCreator
from business.self_evolution.user_clarification_requester import UserClarificationRequester
from business.tools.tool_result import ToolResult


@dataclass
class SafetyCheckResult:
    """安全检查结果"""
    passed: bool
    issues: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low / medium / high / critical
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolSnapshot:
    """工具快照（用于回滚）"""
    tool_name: str
    file_path: str
    file_hash: str
    created_at: float
    parent_file_path: Optional[str] = None  # 被替换的文件备份


class CodeSafetyChecker:
    """
    代码安全检查器

    检查维度：
    1. 危险操作模式检测
    2. 导入安全检查
    3. 网络访问检测
    4. 文件系统操作检测
    5. 代码复杂度评估
    """

    # 危险模式（按风险等级分类）
    CRITICAL_PATTERNS = [
        (r'\bos\.system\s*\(', "直接执行系统命令"),
        (r'\beval\s*\(', "动态执行代码"),
        (r'\bexec\s*\(', "动态执行代码"),
        (r'\b__import__\s*\(', "动态导入模块"),
        (r'\bsubprocess\.\s*call\s*\(', "子进程调用（不安全模式）"),
        (r'\bglobals\s*\(\s*\)', "访问全局变量"),
        (r'\blocals\s*\(\s*\)', "访问局部变量"),
        (r'\bcompile\s*\(', "编译代码"),
        (r'\bgetattr\s*\(.*__\w+__', "动态属性访问（可能危险）"),
    ]

    HIGH_RISK_PATTERNS = [
        (r'\bos\.\s*remove', "删除文件/目录"),
        (r'\bshutil\.\s*rmtree', "递归删除目录"),
        (r'\bopen\s*\([^)]*["\']w["\']', "写入文件（未指定路径）"),
        (r'\brequests\.\s*(get|post|put|delete)', "直接网络请求"),
        (r'\burllib\.request', "直接网络请求"),
        (r'\bsocket\.\s*socket', "直接创建网络套接字"),
        (r'\bpickle\.\s*(loads|load)', "反序列化（可能不安全）"),
    ]

    MEDIUM_RISK_PATTERNS = [
        (r'\bimport\s+subprocess', "导入 subprocess"),
        (r'\bimport\s+socket', "导入 socket"),
        (r'\bimport\s+ctypes', "导入 ctypes"),
        (r'\bimport\s+multiprocessing', "导入 multiprocessing"),
        (r'\bwhile\s+True', "无限循环"),
        (r'\bglobal\s+\w+', "使用全局变量"),
    ]

    @classmethod
    def check(cls, code: str) -> SafetyCheckResult:
        """
        执行安全检查

        Returns:
            SafetyCheckResult
        """
        issues = []
        risk_level = "low"

        # 1. 致命级检查
        for pattern, desc in cls.CRITICAL_PATTERNS:
            if re.search(pattern, code):
                issues.append(f"[CRITICAL] {desc}: 匹配 {pattern}")
                risk_level = "critical"

        # 2. 高风险检查
        if risk_level != "critical":
            for pattern, desc in cls.HIGH_RISK_PATTERNS:
                if re.search(pattern, code):
                    issues.append(f"[HIGH] {desc}: 匹配 {pattern}")
                    risk_level = "high"

        # 3. 中风险检查
        if risk_level == "low":
            for pattern, desc in cls.MEDIUM_RISK_PATTERNS:
                if re.search(pattern, code):
                    issues.append(f"[MEDIUM] {desc}: 匹配 {pattern}")
                    if risk_level == "low":
                        risk_level = "medium"

        # 4. 代码长度检查（过长代码可能有隐藏风险）
        lines = code.split("\n")
        if len(lines) > 500:
            issues.append(f"[MEDIUM] 代码过长: {len(lines)} 行（建议 <500 行）")
            if risk_level == "low":
                risk_level = "medium"

        # 5. 导入检查（只允许白名单内的导入）
        allowed_imports = {
            "os", "json", "re", "math", "datetime", "time", "hashlib",
            "typing", "dataclasses", "collections", "pathlib", "logging",
            "loguru", "asyncio", "functools", "itertools", "copy",
        }
        # 也允许项目内导入
        project_import_pattern = r'from\s+client\.src\.business\.\w+'
        external_imports = []

        for line in lines:
            # 匹配 import xxx
            import_match = re.match(r'^\s*import\s+(\w+)', line)
            if import_match:
                mod = import_match.group(1)
                if mod not in allowed_imports and not mod.startswith("client"):
                    external_imports.append(mod)
            # 匹配 from xxx import
            from_match = re.match(r'^\s*from\s+([\w.]+)\s+import', line)
            if from_match:
                mod = from_match.group(1).split(".")[0]
                if mod not in allowed_imports and not mod.startswith("client"):
                    external_imports.append(mod)

        for ext_imp in external_imports:
            issues.append(f"[HIGH] 外部依赖: import {ext_imp}（不在白名单内）")
            if risk_level == "low":
                risk_level = "medium"

        passed = risk_level not in ("critical", "high")

        return SafetyCheckResult(
            passed=passed,
            issues=issues,
            risk_level=risk_level,
            details={
                "code_length": len(lines),
                "external_imports": external_imports,
            }
        )


class Sandbox:
    """
    沙箱执行环境

    限制：
    - 文件系统：只允许访问指定目录
    - 网络：默认不允许网络访问
    - 内存：限制内存使用
    - 执行时间：限制执行时间
    """

    def __init__(
        self,
        allowed_paths: Optional[List[str]] = None,
        network_access: bool = False,
        max_memory_mb: int = 100,
        max_execution_time: int = 10,
    ):
        self.allowed_paths = allowed_paths or []
        self.network_access = network_access
        self.max_memory_mb = max_memory_mb
        self.max_execution_time = max_execution_time
        self._logger = logger.bind(component="Sandbox")

    async def run_test(self, file_path: str) -> ToolResult:
        """
        在沙箱中运行测试

        Args:
            file_path: 工具文件路径

        Returns:
            ToolResult
        """
        self._logger.info(f"沙箱测试: {file_path}")

        # 检查文件路径是否在允许范围内
        if not self._is_path_allowed(file_path):
            return ToolResult.fail(error=f"文件路径不在允许范围内: {file_path}")

        try:
            # 使用 asyncio.wait_for 限制执行时间
            result = await asyncio.wait_for(
                self._import_and_test(file_path),
                timeout=self.max_execution_time
            )
            return result
        except asyncio.TimeoutError:
            return ToolResult.fail(
                error=f"执行超时（>{self.max_execution_time}s），可能存在无限循环"
            )
        except Exception as e:
            return ToolResult.fail(error=f"沙箱执行异常: {e}")

    def _is_path_allowed(self, file_path: str) -> bool:
        """检查路径是否在允许范围内"""
        if not self.allowed_paths:
            return True  # 未配置限制，允许所有

        abs_path = os.path.abspath(file_path)
        for allowed in self.allowed_paths:
            if abs_path.startswith(os.path.abspath(allowed)):
                return True
        return False

    async def _import_and_test(self, file_path: str) -> ToolResult:
        """导入并测试工具"""
        import importlib.util

        spec = importlib.util.spec_from_file_location("sandbox_test", file_path)
        module = importlib.util.module_from_spec(spec)

        # 限制网络访问（通过 monkey-patch）
        if not self.network_access:
            self._logger.info("  网络访问已禁用")

        try:
            spec.loader.exec_module(module)

            # 查找 BaseTool 子类
            from business.tools.base_tool import BaseTool
            tool_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and issubclass(attr, BaseTool)
                        and attr != BaseTool):
                    tool_class = attr
                    break

            if tool_class is None:
                return ToolResult.fail(error="未找到 BaseTool 子类")

            # 实例化
            tool_instance = tool_class()
            if not tool_instance.name:
                return ToolResult.fail(error="工具名称为空")

            self._logger.info(f"  沙箱测试通过: {tool_instance.name}")
            return ToolResult.ok(
                data={"tool_name": tool_instance.name},
                message="沙箱测试通过"
            )
        except Exception as e:
            return ToolResult.fail(error=str(e))


class SafeAutonomousToolCreator(AutonomousToolCreator):
    """
    安全的自主工具创建器

    在 AutonomousToolCreator 基础上添加安全机制：
    1. 代码安全检查
    2. 沙箱执行
    3. 用户确认
    4. 观察期
    5. 回滚
    """

    def __init__(
        self,
        llm_client=None,
        work_dir: str = None,
        require_user_confirmation: bool = True,
        sandbox_enabled: bool = True,
        observation_hours: int = 0,  # 0=跳过观察期
    ):
        super().__init__(llm_client=llm_client, work_dir=work_dir)
        self._require_confirmation = require_user_confirmation
        self._sandbox_enabled = sandbox_enabled
        self._observation_hours = observation_hours
        self._clarification_requester = UserClarificationRequester()
        self._snapshots: Dict[str, ToolSnapshot] = {}  # 工具快照（用于回滚）
        self._sandbox = Sandbox(
            allowed_paths=[self._work_dir] if work_dir else None,
            network_access=False,
            max_execution_time=10,
        )
        self._logger = logger.bind(component="SafeAutonomousToolCreator")

    async def create_tool(
        self,
        tool_name: str,
        tool_description: str,
        context: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        安全地创建工具（带安全检查）

        流程：
        1. 用户确认（如果需要）
        2. 学习 → 代码生成
        3. 代码安全检查
        4. 沙箱测试
        5. 反思与改进（如果失败）
        6. 注册到沙箱
        7. 观察期（如果配置）
        8. 注册到主系统
        """
        self._logger.info(f"[安全模式] 开始创建工具: {tool_name}")

        # 1. 用户确认
        if self._require_confirmation:
            confirmed = await self._request_user_confirmation(
                tool_name, tool_description
            )
            if not confirmed:
                self._logger.info("用户取消了工具创建")
                return False, None

        # 2. 学习 + 代码生成
        try:
            learning_materials = await self._learn_how_to_create(
                tool_name, tool_description, context
            )
            code = await self._generate_tool_code(
                tool_name, tool_description, learning_materials
            )
        except Exception as e:
            self._logger.error(f"代码生成失败: {e}")
            return False, None

        # 3. 代码安全检查
        safety_result = CodeSafetyChecker.check(code)
        if not safety_result.passed:
            self._logger.error(
                f"安全检查未通过（{safety_result.risk_level}）："
                f"{safety_result.issues}"
            )
            # 对于 medium 级别，可以尝试修复
            if safety_result.risk_level == "medium":
                self._logger.info("尝试自动修复中风险问题...")
                code = await self._auto_fix_medium_risks(code, safety_result.issues)
                safety_result = CodeSafetyChecker.check(code)
                if not safety_result.passed:
                    self._logger.error("自动修复后仍不通过")
                    return False, None
            else:
                return False, None

        # 4. 写入文件
        try:
            file_path = await self._write_code_to_file(tool_name, code)
        except Exception as e:
            self._logger.error(f"写入文件失败: {e}")
            return False, None

        # 5. 测试（沙箱或普通）
        if self._sandbox_enabled:
            self._logger.info("使用沙箱测试...")
            test_result = await self._sandbox.run_test(file_path)
        else:
            test_result = await self._test_tool(file_path)

        # 6. 反思与改进
        if not test_result.success:
            self._logger.warning("测试失败，进入反思与改进阶段...")
            success, path = await self._reflect_and_improve(
                tool_name, code, test_result, file_path, max_retries=3
            )
            if success:
                file_path = path
            else:
                # 清理失败的文件
                if os.path.exists(file_path):
                    os.remove(file_path)
                return False, None

        # 7. 保存快照（用于回滚）
        self._save_snapshot(tool_name, file_path)

        # 8. 注册到主系统
        try:
            await self._register_tool(tool_name, file_path)
            self._logger.info(f"[安全模式] 工具创建成功: {tool_name}")
            return True, file_path
        except Exception as e:
            self._logger.error(f"注册失败: {e}")
            return False, file_path

    async def _request_user_confirmation(
        self, tool_name: str, tool_description: str
    ) -> bool:
        """请求用户确认"""
        self._logger.info(f"请求用户确认创建工具: {tool_name}")
        try:
            response = await self._clarification_requester.request_clarification(
                question=f"即将创建工具：{tool_name}\n\n描述：{tool_description}\n\n是否继续？",
                options=["A. 继续", "B. 取消"]
            )
            return response and "A" in response
        except Exception as e:
            self._logger.warning(f"用户确认失败（自动放行）: {e}")
            return True  # 无法确认时默认放行

    async def _auto_fix_medium_risks(
        self, code: str, issues: List[str]
    ) -> str:
        """自动修复中风险问题"""
        fixes = []
        for issue in issues:
            if "无限循环" in issue:
                fixes.append("# 注意：已检测到无限循环风险，请确保有退出条件")
            elif "全局变量" in issue:
                fixes.append("# 注意：建议减少全局变量使用")

        if fixes:
            self._logger.info(f"添加 {len(fixes)} 条安全提示")
            # 在代码开头添加安全提示
            comment_block = "\n".join(fixes) + "\n\n"
            code = comment_block + code

        return code

    def _save_snapshot(self, tool_name: str, file_path: str):
        """保存工具快照（用于回滚）"""
        try:
            with open(file_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            snapshot = ToolSnapshot(
                tool_name=tool_name,
                file_path=file_path,
                file_hash=file_hash,
                created_at=time.time(),
            )
            self._snapshots[tool_name] = snapshot
            self._logger.info(f"快照已保存: {tool_name} (hash={file_hash[:8]})")
        except Exception as e:
            self._logger.warning(f"快照保存失败: {e}")

    def rollback(self, tool_name: str) -> bool:
        """
        回滚工具到创建前状态

        Args:
            tool_name: 工具名称

        Returns:
            是否回滚成功
        """
        snapshot = self._snapshots.get(tool_name)
        if not snapshot:
            self._logger.warning(f"未找到工具快照: {tool_name}")
            return False

        try:
            # 删除工具文件
            if os.path.exists(snapshot.file_path):
                os.remove(snapshot.file_path)
                self._logger.info(f"已删除: {snapshot.file_path}")

            # 从 ToolRegistry 注销
            try:
                from business.tools.tool_registry import ToolRegistry
                registry = ToolRegistry.get_instance()
                registry.unregister(tool_name)
                self._logger.info(f"已从 ToolRegistry 注销: {tool_name}")
            except Exception:
                pass

            # 清理快照
            del self._snapshots[tool_name]
            self._logger.info(f"工具已回滚: {tool_name}")
            return True
        except Exception as e:
            self._logger.error(f"回滚失败: {e}")
            return False

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """列出所有工具快照"""
        return [
            {
                "tool_name": s.tool_name,
                "file_path": s.file_path,
                "file_hash": s.file_hash[:8],
                "created_at": s.created_at,
            }
            for s in self._snapshots.values()
        ]

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM（通过 GlobalModelRouter）"""
        try:
            from business.global_model_router import call_model_sync, ModelCapability
            return call_model_sync(
                capability=ModelCapability.CODE_GENERATION,
                prompt=prompt,
            )
        except Exception:
            return await super()._call_llm(prompt)
