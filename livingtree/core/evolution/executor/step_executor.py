"""
Step Executor - 单步执行器
负责执行提案的单个步骤，并提供验证和反馈
"""

import os
import re
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"       # 待执行
    RUNNING = "running"        # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    SKIPPED = "skipped"        # 跳过
    VERIFIED = "verified"     # 已验证


@dataclass
class StepExecutionResult:
    """步骤执行结果"""
    step_id: str
    status: StepStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    output: Optional[str] = None
    error: Optional[str] = None
    verification_result: Optional[Dict[str, Any]] = None
    files_changed: List[str] = None
    
    def __post_init__(self):
        if self.files_changed is None:
            self.files_changed = []


class StepExecutor:
    """
    单步执行器
    
    功能：
    1. 执行单个步骤
    2. 步骤验证
    3. 步骤反馈
    4. 条件执行
    """
    
    def __init__(self, project_root: str):
        """
        初始化执行器
        
        Args:
            project_root: 项目根目录
        """
        self.project_root = Path(project_root)
        
        # 验证钩子
        self.verification_hooks: Dict[str, Callable] = {}
        
        logger.info(f"[StepExecutor] 初始化完成")
    
    def execute_step(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> StepExecutionResult:
        """
        执行单个步骤
        
        Args:
            step: 步骤定义
            context: 执行上下文
            
        Returns:
            执行结果
        """
        step_id = step.get("step_id", "unknown")
        action_type = step.get("action_type", "")
        started_at = datetime.now()
        
        logger.info(f"[StepExecutor] 开始执行步骤: {step_id} ({action_type})")
        
        try:
            # 根据操作类型执行
            if action_type == "analysis":
                result = self._execute_analysis(step, context)
            elif action_type == "code_change":
                result = self._execute_code_change(step, context)
            elif action_type == "refactor":
                result = self._execute_refactor(step, context)
            elif action_type == "test":
                result = self._execute_test(step, context)
            elif action_type == "review":
                result = self._execute_review(step, context)
            elif action_type == "config_change":
                result = self._execute_config_change(step, context)
            else:
                result = StepExecutionResult(
                    step_id=step_id,
                    status=StepStatus.FAILED,
                    started_at=started_at,
                    completed_at=datetime.now(),
                    error=f"未知操作类型: {action_type}"
                )
            
            return result
        
        except Exception as e:
            logger.error(f"[StepExecutor] 步骤执行异常: {step_id} - {e}")
            return StepExecutionResult(
                step_id=step_id,
                status=StepStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(),
                error=str(e)
            )
    
    def verify_step(
        self,
        step: Dict[str, Any],
        result: StepExecutionResult
    ) -> StepExecutionResult:
        """
        验证步骤执行结果
        
        Args:
            step: 步骤定义
            result: 执行结果
            
        Returns:
            验证后的结果
        """
        if result.status != StepStatus.COMPLETED:
            return result
        
        step_id = step.get("step_id", "unknown")
        target = step.get("target")
        
        try:
            verification_result = {}
            
            # 代码变更验证
            if step.get("action_type") == "code_change" and target:
                verification_result = self._verify_code_change(target, result)
            
            # 测试验证
            elif step.get("action_type") == "test":
                verification_result = self._verify_test(result)
            
            # 分析验证
            elif step.get("action_type") == "analysis":
                verification_result = self._verify_analysis(result)
            
            result.verification_result = verification_result
            
            if verification_result.get("passed"):
                result.status = StepStatus.VERIFIED
                logger.info(f"[StepExecutor] 步骤验证通过: {step_id}")
            else:
                result.status = StepStatus.FAILED
                logger.warning(
                    f"[StepExecutor] 步骤验证失败: {step_id} - "
                    f"{verification_result.get('message', '未知原因')}"
                )
        
        except Exception as e:
            logger.error(f"[StepExecutor] 验证异常: {step_id} - {e}")
            result.verification_result = {"passed": False, "error": str(e)}
        
        return result
    
    def _execute_analysis(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> StepExecutionResult:
        """执行分析步骤"""
        step_id = step.get("step_id", "unknown")
        description = step.get("description", "")
        target = step.get("target")
        
        started_at = datetime.now()
        output_lines = [f"分析: {description}"]
        
        if target:
            target_path = self.project_root / target
            output_lines.append(f"目标: {target}")
            
            if target_path.exists():
                if target_path.is_file():
                    # 分析文件
                    lines = target_path.stat().st_size
                    output_lines.append(f"文件大小: {lines} bytes")
                elif target_path.is_dir():
                    # 分析目录
                    file_count = sum(1 for _ in target_path.rglob("*") if _.is_file())
                    output_lines.append(f"文件数量: {file_count}")
        
        output = "\n".join(output_lines)
        
        return StepExecutionResult(
            step_id=step_id,
            status=StepStatus.COMPLETED,
            started_at=started_at,
            completed_at=datetime.now(),
            output=output
        )
    
    def _execute_code_change(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> StepExecutionResult:
        """执行代码变更步骤"""
        step_id = step.get("step_id", "unknown")
        target = step.get("target")
        changes = step.get("changes", {})
        started_at = datetime.now()
        
        if not target:
            return StepExecutionResult(
                step_id=step_id,
                status=StepStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(),
                error="缺少目标文件"
            )
        
        target_path = self.project_root / target
        
        # 获取变更内容
        if isinstance(changes, dict):
            content = changes.get("content", "")
            old_str = changes.get("old_str")
            new_str = changes.get("new_str")
        else:
            content = str(changes)
            old_str = None
            new_str = None
        
        files_changed = []
        
        try:
            # 确保父目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            if old_str and new_str:
                # 替换模式
                if target_path.exists():
                    original_content = target_path.read_text(encoding="utf-8")
                    new_content = original_content.replace(old_str, new_str)
                    target_path.write_text(new_content, encoding="utf-8")
                    files_changed.append(str(target_path))
            else:
                # 直接写入
                target_path.write_text(content, encoding="utf-8")
                files_changed.append(str(target_path))
            
            output = f"代码变更完成: {target}\n"
            if old_str:
                output += f"替换: {old_str[:50]}... -> {new_str[:50]}..."
            
            return StepExecutionResult(
                step_id=step_id,
                status=StepStatus.COMPLETED,
                started_at=started_at,
                completed_at=datetime.now(),
                output=output,
                files_changed=files_changed
            )
        
        except Exception as e:
            return StepExecutionResult(
                step_id=step_id,
                status=StepStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(),
                error=str(e)
            )
    
    def _execute_refactor(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> StepExecutionResult:
        """执行重构步骤"""
        # 重构本质上是特殊的代码变更
        return self._execute_code_change(step, context)
    
    def _execute_test(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> StepExecutionResult:
        """执行测试步骤"""
        step_id = step.get("step_id", "unknown")
        target = step.get("target")
        started_at = datetime.now()
        
        output_lines = ["测试执行中..."]
        passed = True
        error = None
        
        try:
            if target:
                target_path = self.project_root / target
                
                # 检查是否是Python文件
                if target_path.suffix == ".py":
                    # 运行pytest
                    result = subprocess.run(
                        ["python", "-m", "pytest", str(target_path), "-v"],
                        capture_output=True,
                        text=True,
                        timeout=300,
                        cwd=self.project_root
                    )
                    
                    output_lines.append(result.stdout)
                    if result.stderr:
                        output_lines.append(result.stderr)
                    
                    passed = result.returncode == 0
                    if not passed:
                        error = f"测试失败，退出码: {result.returncode}"
                else:
                    output_lines.append(f"测试目标: {target}")
                    output_lines.append("测试跳过: 非Python文件")
            else:
                # 运行所有测试
                result = subprocess.run(
                    ["python", "-m", "pytest", "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=600,
                    cwd=self.project_root
                )
                
                output_lines.append(result.stdout)
                passed = result.returncode == 0
                if not passed:
                    error = f"测试失败，退出码: {result.returncode}"
        
        except subprocess.TimeoutExpired:
            error = "测试超时"
            passed = False
        except Exception as e:
            error = str(e)
            passed = False
        
        return StepExecutionResult(
            step_id=step_id,
            status=StepStatus.COMPLETED if passed else StepStatus.FAILED,
            started_at=started_at,
            completed_at=datetime.now(),
            output="\n".join(output_lines),
            error=error
        )
    
    def _execute_review(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> StepExecutionResult:
        """执行代码审查步骤"""
        step_id = step.get("step_id", "unknown")
        description = step.get("description", "")
        started_at = datetime.now()
        
        output_lines = [f"代码审查: {description}"]
        output_lines.append("审查建议:")
        output_lines.append("1. 检查代码风格一致性")
        output_lines.append("2. 验证边界条件处理")
        output_lines.append("3. 确认错误处理逻辑")
        
        return StepExecutionResult(
            step_id=step_id,
            status=StepStatus.COMPLETED,
            started_at=started_at,
            completed_at=datetime.now(),
            output="\n".join(output_lines)
        )
    
    def _execute_config_change(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> StepExecutionResult:
        """执行配置变更步骤"""
        # 配置变更本质上是特殊的代码变更
        return self._execute_code_change(step, context)
    
    def _verify_code_change(
        self,
        target: str,
        result: StepExecutionResult
    ) -> Dict[str, Any]:
        """验证代码变更"""
        target_path = self.project_root / target
        
        if not target_path.exists():
            return {
                "passed": False,
                "message": f"文件不存在: {target}"
            }
        
        # 基本验证：文件可读
        try:
            target_path.read_text(encoding="utf-8")
            return {
                "passed": True,
                "message": "代码变更验证通过"
            }
        except Exception as e:
            return {
                "passed": False,
                "message": f"文件读取失败: {e}"
            }
    
    def _verify_test(self, result: StepExecutionResult) -> Dict[str, Any]:
        """验证测试结果"""
        if result.error:
            return {
                "passed": False,
                "message": f"测试失败: {result.error}"
            }
        
        return {
            "passed": True,
            "message": "测试验证通过"
        }
    
    def _verify_analysis(self, result: StepExecutionResult) -> Dict[str, Any]:
        """验证分析结果"""
        if not result.output:
            return {
                "passed": False,
                "message": "分析无输出"
            }
        
        return {
            "passed": True,
            "message": "分析完成",
            "output_length": len(result.output)
        }
