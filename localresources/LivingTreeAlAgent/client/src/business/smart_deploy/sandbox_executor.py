"""
沙箱模拟执行器 - SandboxExecutor
核心理念：在安全环境中预演部署

功能：
1. 沙箱环境创建
2. 静态分析
3. 交互式模拟
4. 错误预测
5. 性能基准测试
"""

import subprocess
import threading
import time
import json
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SandboxStatus(Enum):
    """沙箱状态"""
    IDLE = "idle"
    CREATING = "creating"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


@dataclass
class SandboxConfig:
    """沙箱配置"""
    max_steps: int = 100
    timeout_seconds: int = 300
    memory_limit_mb: int = 512
    cpu_limit: float = 1.0
    network_enabled: bool = True
    disk_limit_gb: int = 5
    allow_sudo: bool = False


@dataclass
class StepResult:
    """步骤执行结果"""
    step_id: int
    step_name: str
    status: StepStatus
    output: str
    error: Optional[str]
    duration_ms: float
    warnings: List[str]


@dataclass
class SandboxReport:
    """沙箱执行报告"""
    sandbox_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: SandboxStatus
    total_steps: int
    successful_steps: int
    failed_steps: int
    step_results: List[StepResult]
    predicted_errors: List[Dict[str, Any]]
    resource_usage: Dict[str, Any]
    overall_score: float
    recommendations: List[str]


class SandboxExecutor:
    """
    沙箱模拟执行器

    在隔离环境中模拟执行部署脚本
    """

    def __init__(self):
        self._current_sandbox: Optional[SandboxReport] = None
        self._config = SandboxConfig()
        self._listeners: List[Callable] = []
        self._running = False
        self._paused = False
        self._current_step_index = 0

    def set_config(self, config: SandboxConfig):
        """设置沙箱配置"""
        self._config = config

    def execute_sandbox(self, script: str, timeout: int = 60) -> SandboxReport:
        """
        执行沙箱脚本（简化接口）

        Args:
            script: 要执行的脚本内容
            timeout: 超时时间（秒）

        Returns:
            SandboxReport: 执行报告
        """
        return self.simulate(script, timeout=timeout)

    def add_listener(self, listener: Callable):
        """添加执行监听器"""
        self._listeners.append(listener)

    def simulate(
        self,
        script: str,
        language: str = "bash",
        steps: Optional[List] = None,
        progress_callback: Optional[Callable] = None
    ) -> SandboxReport:
        """
        模拟执行脚本

        Args:
            script: 要执行的脚本
            language: 脚本语言
            steps: 部署步骤列表
            progress_callback: 进度回调

        Returns:
            SandboxReport: 执行报告
        """
        sandbox_id = f"sandbox_{int(time.time())}"
        self._current_sandbox = SandboxReport(
            sandbox_id=sandbox_id,
            started_at=datetime.now(),
            completed_at=None,
            status=SandboxStatus.CREATING,
            total_steps=len(steps) if steps else self._count_script_steps(script),
            successful_steps=0,
            failed_steps=0,
            step_results=[],
            predicted_errors=[],
            resource_usage={},
            overall_score=0.0
        )

        self._running = True
        self._paused = False
        self._current_step_index = 0

        try:
            # 阶段1: 静态分析
            self._notify_listeners({"phase": "analysis", "status": "running"})
            static_result = self._static_analysis(script)

            # 阶段2: 预测错误
            self._notify_listeners({"phase": "prediction", "status": "running"})
            predicted_errors = self._predict_errors(script, static_result)
            self._current_sandbox.predicted_errors = predicted_errors

            # 阶段3: 逐步模拟执行
            self._notify_listeners({"phase": "execution", "status": "running"})
            self._current_sandbox.status = SandboxStatus.RUNNING

            if steps:
                for step in steps:
                    if not self._running:
                        break
                    while self._paused:
                        time.sleep(0.1)
                    result = self._simulate_step(step)
                    self._current_sandbox.step_results.append(result)
                    if result.status == StepStatus.SUCCESS:
                        self._current_sandbox.successful_steps += 1
                    elif result.status == StepStatus.FAILED:
                        self._current_sandbox.failed_steps += 1
                    self._current_step_index += 1
                    if progress_callback:
                        progress_callback(result)
            else:
                # 按行模拟脚本
                self._simulate_script_lines(script, progress_callback)

            # 完成
            self._current_sandbox.status = SandboxStatus.COMPLETED
            self._current_sandbox.completed_at = datetime.now()
            self._current_sandbox.overall_score = self._calculate_score()
            self._current_sandbox.recommendations = self._generate_recommendations()

        except Exception as e:
            logger.error(f"Sandbox simulation failed: {e}")
            self._current_sandbox.status = SandboxStatus.FAILED
            self._current_sandbox.completed_at = datetime.now()

        self._running = False
        return self._current_sandbox

    def _static_analysis(self, script: str) -> Dict[str, Any]:
        """静态分析脚本"""
        result = {
            "total_lines": len(script.split('\n')),
            "dangerous_commands": [],
            "suspicious_patterns": [],
            "required_permissions": [],
            "estimated_resources": {}
        }

        dangerous_patterns = {
            r'rm\s+-rf': "危险: 递归删除",
            r'drop\s+table': "危险: 删除数据库表",
            r'delete\s+from': "危险: 删除数据",
            r'chmod\s+777': "危险: 过度开放权限",
            r'curl.*\|.*sh': "危险: 管道执行远程脚本",
            r'wget.*\|.*sh': "危险: 下载并执行",
            r'eval\s*\(': "危险: 动态代码执行",
            r'exec\s*\(': "危险: 命令执行"
        }

        for pattern, description in dangerous_patterns.items():
            matches = re.finditer(pattern, script, re.IGNORECASE)
            for match in matches:
                result["dangerous_commands"].append({
                    "pattern": pattern,
                    "description": description,
                    "line": self._get_line_number(script, match.start())
                })

        # 检测所需权限
        if 'sudo' in script.lower():
            result["required_permissions"].append("sudo")
        if 'chmod' in script.lower():
            result["required_permissions"].append("chmod")
        if 'systemctl' in script.lower():
            result["required_permissions"].append("systemctl")

        # 估算资源
        result["estimated_resources"] = {
            "cpu_cores": 1,
            "memory_mb": 256,
            "disk_gb": 1,
            "estimated_time_seconds": result["total_lines"] * 0.5
        }

        return result

    def _predict_errors(self, script: str, static_result: Dict) -> List[Dict[str, Any]]:
        """预测可能的错误"""
        errors = []

        # 基于静态分析结果预测
        for cmd in static_result.get("dangerous_commands", []):
            errors.append({
                "type": "dangerous_command",
                "severity": "high",
                "description": cmd["description"],
                "line": cmd["line"],
                "suggestion": "确认此操作是必需的，并做好回滚准备"
            })

        # 基于模式预测
        if 'pip install' in script and '-r requirements.txt' not in script:
            errors.append({
                "type": "missing_requirements",
                "severity": "medium",
                "description": "直接使用pip install而非requirements.txt",
                "suggestion": "建议使用 requirements.txt 管理依赖版本"
            })

        if 'npm install' in script and '--save' not in script:
            errors.append({
                "type": "missing_save_flag",
                "severity": "low",
                "description": "npm install 未指定保存依赖",
                "suggestion": "建议使用 npm install --save 或 npm install -S"
            })

        if 'chmod' in script and '777' in script:
            errors.append({
                "type": "security_risk",
                "severity": "high",
                "description": "使用 chmod 777 权限",
                "suggestion": "使用更严格的权限，如 755 或 644"
            })

        return errors

    def _simulate_step(self, step) -> StepResult:
        """模拟执行单个步骤（沙箱模式）

        在沙箱中执行，不会真正修改系统状态，但会实际运行命令来验证。
        使用容器或虚拟机隔离环境。
        """
        import shlex

        start_time = time.time()
        output = []
        warnings = []
        status = StepStatus.SUCCESS

        try:
            # 检查权限
            if hasattr(step, 'required_permissions'):
                for perm in step.required_permissions:
                    if perm == "sudo" and not self._config.allow_sudo:
                        warnings.append(f"需要 {perm} 权限，但沙箱配置不允许")
                        status = StepStatus.WARNING

            # 在沙箱中执行命令
            if hasattr(step, 'command'):
                cmd = step.command

                # 检查危险命令
                dangerous = self._check_dangerous_command(cmd)
                if dangerous:
                    warnings.append(f"警告: {dangerous}")
                    status = StepStatus.WARNING

                # 真实执行（沙箱模式 - 使用安全的方式）
                result = self._execute_in_sandbox(cmd)

                output.append(f"$ {cmd}")
                output.append(result["output"])

                if not result["success"]:
                    status = StepStatus.FAILED
                    output.append(f"[失败] {result['error']}")
                else:
                    output.append(f"[成功]")

            # 验证命令
            if hasattr(step, 'verify_command') and step.verify_command:
                verify_result = self._execute_in_sandbox(step.verify_command)
                if verify_result["success"]:
                    output.append(f"[验证通过] {step.verify_command}")
                else:
                    warnings.append("验证命令执行失败")
                    output.append(f"[验证失败] {step.verify_command}")

            # 模拟耗时
            if hasattr(step, 'estimated_time_seconds'):
                time.sleep(min(step.estimated_time_seconds, 1))

        except Exception as e:
            status = StepStatus.FAILED
            output.append(f"[失败] {str(e)}")

        duration_ms = (time.time() - start_time) * 1000

        return StepResult(
            step_id=step.step_id if hasattr(step, 'step_id') else 0,
            step_name=step.name if hasattr(step, 'name') else "Unknown",
            status=status,
            output='\n'.join(output),
            error=None if status == StepStatus.SUCCESS else output[-1] if output else "执行失败",
            duration_ms=duration_ms,
            warnings=warnings
        )

    def _check_dangerous_command(self, command: str) -> str:
        """检查危险命令"""
        import re

        dangerous_patterns = {
            r'rm\s+-rf\s+/': "危险: 递归删除根目录",
            r'drop\s+database': "危险: 删除数据库",
            r'drop\s+table': "危险: 删除数据表",
            r'truncate\s+': "危险: 清空表数据",
            r'delete\s+from\s+\w+\s*;?\s*$': "危险: 删除所有数据",
            r'chmod\s+777': "危险: 过度开放权限",
            r'curl.*\|.*sh': "危险: 管道执行远程脚本",
            r'wget.*\|.*sh': "危险: 下载并执行脚本",
            r':(){:|:&};:': "危险: Fork炸弹",
            r'shutdown|reboot': "危险: 系统关机/重启命令"
        }

        for pattern, desc in dangerous_patterns.items():
            if re.search(pattern, command, re.IGNORECASE):
                return desc
        return None

    def _execute_in_sandbox(self, command: str) -> dict:
        """在沙箱中执行命令

        优先使用docker沙箱，其次使用本地安全模式
        """
        import subprocess
        import shlex

        # 检查是否可以使用docker沙箱
        if self._can_use_docker_sandbox():
            return self._execute_in_docker(command)

        # 使用本地安全模式（限制性执行）
        return self._execute_safely(command)

    def _can_use_docker_sandbox(self) -> bool:
        """检查是否可以使用Docker沙箱"""
        try:
            result = subprocess.run(
                ["docker", "info"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def _execute_in_docker(self, command: str) -> dict:
        """在Docker沙箱中执行命令"""
        import subprocess
        import shlex

        try:
            safe_cmd = shlex.quote(command)
            docker_cmd = [
                "docker", "run", "--rm",
                "--network", "none" if not self._config.network_enabled else "bridge",
                "--memory", f"{self._config.memory_limit_mb}m",
                "--cpus", str(self._config.cpu_limit),
                "--read-only" if not self._config.allow_sudo else "",
                "alpine:latest", "sh", "-c", safe_cmd
            ]

            # 过滤空字符串
            docker_cmd = [c for c in docker_cmd if c]

            result = subprocess.run(
                docker_cmd, capture_output=True, text=True,
                timeout=min(self._config.timeout_seconds, 60)
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip() if result.stderr else None
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "执行超时"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _execute_safely(self, command: str) -> dict:
        """安全模式执行（不做真实操作，仅分析）"""
        import re

        # 分析命令是否安全
        dangerous = self._check_dangerous_command(command)

        if dangerous:
            return {
                "success": False,
                "output": "",
                "error": f"沙箱拦截危险命令: {dangerous}"
            }

        # 对于读命令，允许执行
        safe_read_commands = ['echo', 'pwd', 'whoami', 'ls', 'cat', 'grep', 'find', 'which', 'type', 'id']

        cmd_parts = command.strip().split()
        if cmd_parts:
            base_cmd = cmd_parts[0]

            if base_cmd in safe_read_commands:
                # 安全的读命令，模拟执行
                return {
                    "success": True,
                    "output": f"[沙箱模拟] {command} - 命令已被记录但未实际执行",
                    "error": None
                }
            elif any(cmd in command for cmd in ['install', 'update', 'upgrade', 'remove', 'delete']):
                # 包管理命令需要特殊权限
                return {
                    "success": True,
                    "output": f"[沙箱模拟] {command} - 包管理命令需要Docker支持",
                    "error": None
                }
            else:
                # 其他命令模拟执行
                return {
                    "success": True,
                    "output": f"[沙箱模拟] {command}",
                    "error": None
                }

        return {
            "success": True,
            "output": f"[沙箱模拟] {command}",
            "error": None
        }

    def _simulate_script_lines(self, script: str, progress_callback: Optional[Callable]):
        """执行脚本行（在沙箱中）"""
        import re

        lines = script.split('\n')
        line_num = 0

        for i, line in enumerate(lines):
            if not self._running:
                break
            while self._paused:
                time.sleep(0.1)

            line = line.strip()
            if not line or line.startswith('#'):
                continue

            line_num += 1

            # 检查危险命令
            dangerous = self._check_dangerous_command(line)
            warnings = []
            status = StepStatus.SUCCESS
            output = f"$ {line}"

            if dangerous:
                warnings.append(dangerous)
                status = StepStatus.WARNING
                output += f"\n[警告] {dangerous}"

            # 执行命令
            result = self._execute_in_sandbox(line)

            if result["success"]:
                output += f"\n[成功] {result['output'][:100] if result['output'] else '完成'}"
            else:
                status = StepStatus.FAILED
                output += f"\n[失败] {result['error']}"

            step_result = StepResult(
                step_id=line_num,
                step_name=f"行 {i + 1}: {line[:30]}...",
                status=status,
                output=output,
                error=result["error"] if not result["success"] else None,
                duration_ms=100,
                warnings=warnings
            )

            self._current_sandbox.step_results.append(step_result)
            if progress_callback:
                progress_callback(step_result)

    def _count_script_steps(self, script: str) -> int:
        """统计脚本步数"""
        lines = [l.strip() for l in script.split('\n')]
        return len([l for l in lines if l and not l.startswith('#')])

    def _get_line_number(self, script: str, char_index: int) -> int:
        """获取字符位置对应的行号"""
        return script[:char_index].count('\n') + 1

    def _calculate_score(self) -> float:
        """计算综合评分"""
        if not self._current_sandbox:
            return 0.0

        score = 100.0

        # 扣除失败步骤
        score -= self._current_sandbox.failed_steps * 10

        # 扣除危险命令
        score -= len(self._current_sandbox.predicted_errors) * 5

        # 扣除警告
        for result in self._current_sandbox.step_results:
            score -= len(result.warnings) * 2

        return max(0.0, min(100.0, score))

    def _generate_recommendations(self) -> List[str]:
        """生成建议"""
        recommendations = []

        if self._current_sandbox.failed_steps > 0:
            recommendations.append(f"有 {self._current_sandbox.failed_steps} 个步骤失败，建议检查脚本语法")

        if len(self._current_sandbox.predicted_errors) > 0:
            recommendations.append("检测到潜在危险命令，请确认操作必要性")

        if self._current_sandbox.overall_score >= 90:
            recommendations.append("脚本质量良好，可以安全执行")
        elif self._current_sandbox.overall_score >= 70:
            recommendations.append("脚本存在一些小问题，建议优化后执行")
        else:
            recommendations.append("脚本存在较多问题，建议仔细审核后再执行")

        return recommendations

    def pause(self):
        """暂停执行"""
        self._paused = True

    def resume(self):
        """恢复执行"""
        self._paused = False

    def stop(self):
        """停止执行"""
        self._running = False
        if self._current_sandbox:
            self._current_sandbox.status = SandboxStatus.STOPPED
            self._current_sandbox.completed_at = datetime.now()

    def _notify_listeners(self, event: Dict):
        """通知监听器"""
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Listener error: {e}")

    def get_current_status(self) -> Optional[SandboxReport]:
        """获取当前状态"""
        return self._current_sandbox


# 全局实例
sandbox_executor = SandboxExecutor()
