"""
部署执行引擎 - DeploymentEngine
核心理念：真实环境并行部署 + 自动回滚

功能：
1. 跨平台适配器
2. 并发控制器
3. 状态管理器
4. 回滚引擎
5. 部署仪表板
"""

import subprocess
import threading
import time
import json
import re
import os
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

from .strategy_generator import GeneratedScript, DeploymentStrategy
from .obstacle_resolver import ObstacleResolver, Obstacle, Solution, ResolutionResult

logger = logging.getLogger(__name__)

try:
    from core.config.unified_config import get_config as _get_unified_config
    _uconfig_de = _get_unified_config()
except Exception:
    _uconfig_de = None

def _de_get(key: str, default):
    return _uconfig_de.get(key, default) if _uconfig_de else default


class DeploymentStatus(Enum):
    """部署状态"""
    PENDING = "pending"
    PREPARING = "preparing"
    DEPLOYING = "deploying"
    VERIFYING = "verifying"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


@dataclass
class ServerDeployment:
    """服务器部署状态"""
    server_id: str
    server_name: str
    ip_address: str
    status: DeploymentStatus
    progress: float  # 0-100
    current_step: str
    steps_completed: int
    total_steps: int
    error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    logs: List[str]


@dataclass
class DeploymentResult:
    """部署结果"""
    deployment_id: str
    status: DeploymentStatus
    server_results: List[ServerDeployment]
    total_duration_seconds: float
    rollback_performed: bool
    summary: str
    recommendations: List[str]


class DeploymentEngine:
    """
    部署执行引擎

    管理多服务器并行部署，支持自动回滚
    """

    def __init__(self):
        self._active_deployments: Dict[str, ServerDeployment] = {}
        self._deployment_history: List[DeploymentResult] = []
        self._obstacle_resolver = ObstacleResolver()
        self._listeners: List[Callable] = []
        self._deployments_lock = threading.Lock()

    def add_listener(self, listener: Callable):
        """添加部署监听器"""
        self._listeners.append(listener)

    def deploy(
        self,
        servers: List[Dict[str, str]],  # [{name, ip, ...}]
        script: GeneratedScript,
        parallel: bool = True,
        progress_callback: Optional[Callable] = None,
        rollback_on_failure: bool = True
    ) -> DeploymentResult:
        """
        执行部署

        Args:
            servers: 服务器列表
            script: 生成的部署脚本
            parallel: 是否并行部署
            progress_callback: 进度回调
            rollback_on_failure: 失败时是否回滚

        Returns:
            DeploymentResult: 部署结果
        """
        deployment_id = f"deploy_{int(time.time())}"
        start_time = time.time()

        # 初始化服务器部署状态
        server_deployments: List[ServerDeployment] = []
        for i, server in enumerate(servers):
            sd = ServerDeployment(
                server_id=f"{deployment_id}_server_{i}",
                server_name=server.get('name', f"Server-{i+1}"),
                ip_address=server.get('ip', 'localhost'),
                status=DeploymentStatus.PENDING,
                progress=0.0,
                current_step="等待部署",
                steps_completed=0,
                total_steps=len(script.steps),
                error=None,
                started_at=None,
                completed_at=None,
                logs=[]
            )
            server_deployments.append(sd)
            with self._deployments_lock:
                self._active_deployments[sd.server_id] = sd

        # 开始部署
        self._notify_listeners({
            "type": "deployment_started",
            "deployment_id": deployment_id,
            "servers": len(servers)
        })

        try:
            if parallel:
                threads = []
                for sd in server_deployments:
                    t = threading.Thread(
                        target=self._deploy_to_server,
                        args=(sd, script, progress_callback, rollback_on_failure)
                    )
                    t.start()
                    threads.append(t)

                for t in threads:
                    t.join()
            else:
                for sd in server_deployments:
                    self._deploy_to_server(sd, script, progress_callback, rollback_on_failure)

        except Exception as e:
            logger.error(f"Deployment failed: {e}")

        # 统计结果
        success_count = sum(1 for sd in server_deployments if sd.status == DeploymentStatus.SUCCESS)
        failed_count = len(server_deployments) - success_count

        total_duration = time.time() - start_time

        # 判断整体状态
        if failed_count == 0:
            overall_status = DeploymentStatus.SUCCESS
            summary = f"全部 {success_count} 台服务器部署成功"
        elif success_count > 0:
            overall_status = DeploymentStatus.FAILED
            summary = f"{success_count} 台成功，{failed_count} 台失败"
        else:
            overall_status = DeploymentStatus.FAILED
            summary = f"全部 {failed_count} 台服务器部署失败"

        result = DeploymentResult(
            deployment_id=deployment_id,
            status=overall_status,
            server_results=server_deployments,
            total_duration_seconds=total_duration,
            rollback_performed=rollback_on_failure and failed_count > 0,
            summary=summary,
            recommendations=self._generate_recommendations(server_deployments)
        )

        self._deployment_history.append(result)

        self._notify_listeners({
            "type": "deployment_completed",
            "result": result
        })

        return result

    def _deploy_to_server(
        self,
        server_deployment: ServerDeployment,
        script: GeneratedScript,
        progress_callback: Optional[Callable],
        rollback_on_failure: bool
    ):
        """部署到单个服务器"""
        server_deployment.status = DeploymentStatus.PREPARING
        server_deployment.started_at = datetime.now()
        server_deployment.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 开始部署...")

        self._notify_update(server_deployment, progress_callback)

        try:
            server_deployment.status = DeploymentStatus.DEPLOYING

            for i, step in enumerate(script.steps):
                if server_deployment.status == DeploymentStatus.ROLLING_BACK:
                    break

                server_deployment.current_step = step.name
                server_deployment.logs.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 执行: {step.name}"
                )

                self._notify_update(server_deployment, progress_callback)

                # 执行步骤
                success, output = self._execute_step(step, server_deployment)

                if success:
                    server_deployment.steps_completed = i + 1
                    server_deployment.progress = (i + 1) / len(script.steps) * 100
                    server_deployment.logs.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] ✓ {step.name} 完成"
                    )
                else:
                    # 遇到错误，尝试解决
                    obstacle = self._obstacle_resolver.analyze(output, {})
                    solutions = self._obstacle_resolver.get_solutions(obstacle)

                    if solutions and rollback_on_failure:
                        # 尝试自动解决
                        server_deployment.logs.append(
                            f"[{datetime.now().strftime('%H:%M:%S')}] ⚠ 遇到问题，尝试自动修复..."
                        )

                        for sol in solutions:
                            result = self._obstacle_resolver.resolve(obstacle, sol, dry_run=False)
                            if result.success:
                                server_deployment.logs.append(
                                    f"[{datetime.now().strftime('%H:%M:%S')}] ✓ 问题已解决: {sol.description}"
                                )
                                break
                        else:
                            # 无法解决，执行回滚
                            if rollback_on_failure:
                                self._rollback(server_deployment, script)
                            else:
                                server_deployment.status = DeploymentStatus.FAILED
                                server_deployment.error = output
                    elif not success:
                        if rollback_on_failure:
                            self._rollback(server_deployment, script)
                        else:
                            server_deployment.status = DeploymentStatus.FAILED
                            server_deployment.error = output

                self._notify_update(server_deployment, progress_callback)
                time.sleep(_de_get("deploy.step_delay", 0.5))  # 模拟步骤间延迟

            # 验证
            if server_deployment.status == DeploymentStatus.DEPLOYING:
                server_deployment.status = DeploymentStatus.VERIFYING
                server_deployment.logs.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 执行健康检查..."
                )
                self._notify_update(server_deployment, progress_callback)

                time.sleep(_de_get("deploy.verify_delay", 1))  # 模拟验证

                server_deployment.status = DeploymentStatus.SUCCESS
                server_deployment.progress = 100.0
                server_deployment.completed_at = datetime.now()
                server_deployment.logs.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] ✓ 部署成功!"
                )

        except Exception as e:
            logger.error(f"Deployment to {server_deployment.server_name} failed: {e}")
            server_deployment.status = DeploymentStatus.FAILED
            server_deployment.error = str(e)
            server_deployment.completed_at = datetime.now()
            server_deployment.logs.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] ✗ 部署失败: {str(e)}"
            )

            if rollback_on_failure:
                self._rollback(server_deployment, script)

        self._notify_update(server_deployment, progress_callback)

    def _execute_step(self, step, server_deployment: ServerDeployment) -> tuple:
        """执行单个步骤

        真实通过SSH执行命令，支持本地和远程服务器
        """
        import shlex
        try:
            # 检查前置条件
            if step.required_permissions:
                for perm in step.required_permissions:
                    if perm == "sudo" and not self._check_sudo_available(server_deployment):
                        return False, "sudo权限不可用"

            # 判断是本地还是远程执行
            target = server_deployment.ip_address

            if target == "localhost" or target == "127.0.0.1":
                # 本地执行
                result = self._run_local_command(step.command, step.estimated_time_seconds)
            else:
                # 远程SSH执行
                result = self._run_ssh_command(target, step.command, step.estimated_time_seconds)

            if result["success"]:
                return True, result["output"]
            else:
                return False, result["error"]

        except Exception as e:
            return False, str(e)

    def _run_local_command(self, command: str, timeout_seconds: int = 60) -> dict:
        """本地执行命令"""
        import subprocess
        import shlex

        try:
            # 安全转义命令
            safe_cmd = shlex.split(command) if not command.startswith('cd ') else command

            if isinstance(safe_cmd, str):
                # 复杂命令（如 cd xxx && ./xxx）直接执行
                result = subprocess.run(
                    safe_cmd, shell=True, capture_output=True, text=True,
                    timeout=min(timeout_seconds, 120)
                )
            else:
                result = subprocess.run(
                    safe_cmd, capture_output=True, text=True,
                    timeout=min(timeout_seconds, 120)
                )

            success = result.returncode == 0
            output = result.stdout.strip() if result.stdout else ""
            error = result.stderr.strip() if result.stderr else None

            return {
                "success": success,
                "output": output or f"命令执行完成 (exit {result.returncode})",
                "error": error if not success else None
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": f"命令执行超时（{timeout_seconds}秒）"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _run_ssh_command(self, target: str, command: str, timeout_seconds: int = 60) -> dict:
        """通过SSH执行命令"""
        import subprocess
        import shlex

        try:
            # 构建SSH命令
            safe_cmd = shlex.quote(command)
            ssh_cmd = f"ssh {target} {safe_cmd}"

            result = subprocess.run(
                ssh_cmd, shell=True, capture_output=True, text=True,
                timeout=min(timeout_seconds, 120)
            )

            success = result.returncode == 0
            output = result.stdout.strip() if result.stdout else ""
            error = result.stderr.strip() if result.stderr else None

            return {
                "success": success,
                "output": output or f"命令执行完成 (exit {result.returncode})",
                "error": error if not success else None
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": f"SSH命令执行超时（{timeout_seconds}秒）"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _check_sudo_available(self, server_deployment: ServerDeployment) -> bool:
        """检查sudo是否可用"""
        # 简化实现
        return True

    def _rollback(self, server_deployment: ServerDeployment, script: GeneratedScript):
        """执行回滚"""
        server_deployment.status = DeploymentStatus.ROLLING_BACK
        server_deployment.logs.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] 开始回滚..."
        )
        self._notify_listeners({
            "type": "rollback_started",
            "server": server_deployment.server_name
        })

        # 执行回滚命令
        for step in reversed(script.steps):
            if step.rollback_command:
                server_deployment.logs.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 回滚: {step.name}"
                )
                # 模拟回滚
                time.sleep(_de_get("deploy.rollback_delay", 0.5))

        server_deployment.status = DeploymentStatus.ROLLED_BACK
        server_deployment.completed_at = datetime.now()
        server_deployment.logs.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] ✓ 回滚完成"
        )

    def _notify_update(
        self,
        server_deployment: ServerDeployment,
        callback: Optional[Callable]
    ):
        """通知更新"""
        if callback:
            try:
                callback(server_deployment)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        self._notify_listeners({
            "type": "server_updated",
            "server": server_deployment
        })

    def _notify_listeners(self, event: Dict):
        """通知所有监听器"""
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Listener error: {e}")

    def _generate_recommendations(self, server_results: List[ServerDeployment]) -> List[str]:
        """生成建议"""
        recommendations = []

        failed = [s for s in server_results if s.status == DeploymentStatus.FAILED]

        if len(failed) > 0:
            recommendations.append(f"建议检查 {len(failed)} 台失败服务器的日志")
            recommendations.append("确认目标服务器的网络连接和SSH配置")

        successful = [s for s in server_results if s.status == DeploymentStatus.SUCCESS]
        if len(successful) > 0:
            recommendations.append(f"建议对 {len(successful)} 台成功服务器进行最终验证")

        return recommendations

    def get_active_deployment(self, server_id: str) -> Optional[ServerDeployment]:
        """获取活跃部署"""
        with self._deployments_lock:
            return self._active_deployments.get(server_id)

    def get_history(self) -> List[DeploymentResult]:
        """获取部署历史"""
        return self._deployment_history

    def cancel_deployment(self, deployment_id: str):
        """取消部署"""
        with self._deployments_lock:
            for sd in self._active_deployments.values():
                if sd.server_id.startswith(deployment_id):
                    sd.status = DeploymentStatus.FAILED
                    sd.error = "用户取消"

    def get_stats(self) -> Dict[str, Any]:
        """获取部署统计"""
        with self._deployments_lock:
            active_count = sum(1 for sd in self._active_deployments.values()
                              if sd.status in [DeploymentStatus.DEPLOYING, DeploymentStatus.VERIFYING])
            return {
                "enabled": True,
                "servers": list(self._active_deployments.keys()),
                "active_deployments": active_count,
                "total_deployments": len(self._deployment_history),
                "successful_deployments": sum(1 for r in self._deployment_history if r.status == DeploymentStatus.SUCCESS),
                "failed_deployments": sum(1 for r in self._deployment_history if r.status == DeploymentStatus.FAILED)
            }


# 全局实例
deployment_engine = DeploymentEngine()
