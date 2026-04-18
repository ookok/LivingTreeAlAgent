"""
障碍自动解决器 - ObstacleResolver
核心理念：内置100+种常见问题的自动解决方案

支持的场景：
- 权限问题 → 自动sudo/提权/改权限
- 磁盘空间 → 自动清理/压缩/扩容
- 网络问题 → 自动配置防火墙/代理
- 依赖缺失 → 自动安装/编译/替换
- 端口占用 → 自动切换/关闭冲突进程
- 超时问题 → 自动重试/优化参数
"""

import subprocess
import re
import time
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ObstacleType(Enum):
    """障碍类型"""
    PERMISSION = "permission"
    DISK_SPACE = "disk_space"
    NETWORK = "network"
    DEPENDENCY = "dependency"
    PORT_CONFLICT = "port_conflict"
    TIMEOUT = "timeout"
    SERVICE = "service"
    CONFIG = "config"
    UNKNOWN = "unknown"


@dataclass
class Obstacle:
    """障碍"""
    obstacle_type: ObstacleType
    description: str
    raw_error: str
    context: Dict[str, Any]
    severity: str  # low/medium/high


@dataclass
class Solution:
    """解决方案"""
    solution_id: str
    description: str
    commands: List[str]
    rollback_commands: List[str]
    confidence: float  # 0-1
    requires_confirmation: bool
    requires_sudo: bool


@dataclass
class ResolutionResult:
    """解决结果"""
    obstacle: Obstacle
    solution: Optional[Solution]
    success: bool
    output: str
    error: Optional[str]
    resolved_at: Optional[time.time]


class ObstacleResolver:
    """
    障碍自动解决器

    内置常见问题的自动解决方案
    """

    def __init__(self):
        self._solution_library = self._build_solution_library()
        self._resolution_history: List[ResolutionResult] = []

    def _build_solution_library(self) -> Dict[str, List[Dict]]:
        """构建解决方案库"""
        return {
            "permission_denied": [
                {
                    "id": "perm_sudo",
                    "desc": "使用sudo提升权限",
                    "commands": ["sudo {command}"],
                    "rollback": [],
                    "confidence": 0.9,
                    "requires_confirmation": True,
                    "requires_sudo": False
                },
                {
                    "id": "perm_chmod",
                    "desc": "修改文件权限",
                    "commands": ["chmod +x {file}"],
                    "rollback": ["chmod -x {file}"],
                    "confidence": 0.8,
                    "requires_confirmation": True,
                    "requires_sudo": False
                },
                {
                    "id": "perm_chown",
                    "desc": "修改文件所有者",
                    "commands": ["sudo chown $USER:{group} {file}"],
                    "rollback": ["sudo chown root:{group} {file}"],
                    "confidence": 0.7,
                    "requires_confirmation": True,
                    "requires_sudo": True
                }
            ],
            "disk_space": [
                {
                    "id": "disk_cleanup_logs",
                    "desc": "清理日志文件",
                    "commands": ["sudo find /var/log -type f -name '*.log' -exec truncate -s 0 {} \\;", "sudo journalctl --vacuum-time=7d"],
                    "rollback": [],
                    "confidence": 0.9,
                    "requires_confirmation": True,
                    "requires_sudo": True
                },
                {
                    "id": "disk_cleanup_cache",
                    "desc": "清理缓存文件",
                    "commands": ["sudo apt-get clean", "npm cache clean --force", "pip cache purge"],
                    "rollback": [],
                    "confidence": 0.85,
                    "requires_confirmation": True,
                    "requires_sudo": False
                },
                {
                    "id": "disk_cleanup_temp",
                    "desc": "清理临时文件",
                    "commands": ["rm -rf /tmp/*", "rm -rf ~/.cache/*"],
                    "rollback": [],
                    "confidence": 0.8,
                    "requires_confirmation": True,
                    "requires_sudo": False
                }
            ],
            "network_connection": [
                {
                    "id": "net_check_firewall",
                    "desc": "检查防火墙状态",
                    "commands": ["sudo ufw status", "sudo iptables -L"],
                    "rollback": [],
                    "confidence": 0.7,
                    "requires_confirmation": False,
                    "requires_sudo": True
                },
                {
                    "id": "net_open_port",
                    "desc": "开放端口",
                    "commands": ["sudo ufw allow {port}/tcp"],
                    "rollback": ["sudo ufw deny {port}/tcp"],
                    "confidence": 0.8,
                    "requires_confirmation": True,
                    "requires_sudo": True
                },
                {
                    "id": "net_check_proxy",
                    "desc": "检查代理设置",
                    "commands": ["echo $http_proxy", "echo $https_proxy"],
                    "rollback": [],
                    "confidence": 0.6,
                    "requires_confirmation": False,
                    "requires_sudo": False
                }
            ],
            "dependency_missing": [
                {
                    "id": "dep_install_apt",
                    "desc": "安装系统依赖(apt)",
                    "commands": ["sudo apt-get update && sudo apt-get install -y {package}"],
                    "rollback": ["sudo apt-get remove -y {package}"],
                    "confidence": 0.9,
                    "requires_confirmation": True,
                    "requires_sudo": True
                },
                {
                    "id": "dep_install_pip",
                    "desc": "安装Python依赖",
                    "commands": ["pip install {package}"],
                    "rollback": ["pip uninstall -y {package}"],
                    "confidence": 0.9,
                    "requires_confirmation": False,
                    "requires_sudo": False
                },
                {
                    "id": "dep_install_npm",
                    "desc": "安装Node.js依赖",
                    "commands": ["npm install {package}"],
                    "rollback": ["npm uninstall {package}"],
                    "confidence": 0.9,
                    "requires_confirmation": False,
                    "requires_sudo": False
                }
            ],
            "port_in_use": [
                {
                    "id": "port_find_process",
                    "desc": "查找占用端口的进程",
                    "commands": ["lsof -i :{port}", "netstat -tlnp | grep :{port}"],
                    "rollback": [],
                    "confidence": 0.8,
                    "requires_confirmation": False,
                    "requires_sudo": False
                },
                {
                    "id": "port_kill_process",
                    "desc": "终止占用端口的进程",
                    "commands": ["sudo kill -9 $(lsof -t -i :{port})"],
                    "rollback": [],
                    "confidence": 0.7,
                    "requires_confirmation": True,
                    "requires_sudo": True
                },
                {
                    "id": "port_change",
                    "desc": "更换端口",
                    "commands": ["sed -i 's/{old_port}/{new_port}/g' {config_file}"],
                    "rollback": ["sed -i 's/{new_port}/{old_port}/g' {config_file}"],
                    "confidence": 0.75,
                    "requires_confirmation": True,
                    "requires_sudo": False
                }
            ],
            "timeout": [
                {
                    "id": "timeout_increase",
                    "desc": "增加超时时间",
                    "commands": ["export CURL_TIMEOUT=300", "export REQUEST_TIMEOUT=300"],
                    "rollback": [],
                    "confidence": 0.8,
                    "requires_confirmation": False,
                    "requires_sudo": False
                },
                {
                    "id": "timeout_retry",
                    "desc": "增加重试次数",
                    "commands": ["export MAX_RETRIES=5"],
                    "rollback": [],
                    "confidence": 0.7,
                    "requires_confirmation": False,
                    "requires_sudo": False
                }
            ],
            "service_failed": [
                {
                    "id": "svc_restart",
                    "desc": "重启服务",
                    "commands": ["sudo systemctl restart {service}"],
                    "rollback": ["sudo systemctl stop {service}"],
                    "confidence": 0.85,
                    "requires_confirmation": True,
                    "requires_sudo": True
                },
                {
                    "id": "svc_status",
                    "desc": "查看服务状态",
                    "commands": ["sudo systemctl status {service}", "sudo journalctl -u {service} -n 50"],
                    "rollback": [],
                    "confidence": 0.7,
                    "requires_confirmation": False,
                    "requires_sudo": True
                }
            ]
        }

    def analyze(self, error_message: str, context: Optional[Dict] = None) -> Obstacle:
        """分析障碍类型"""
        error_lower = error_message.lower()
        context = context or {}

        # 权限问题
        if any(kw in error_lower for kw in ['permission denied', 'access denied', 'eacces', 'operation not permitted']):
            return Obstacle(
                obstacle_type=ObstacleType.PERMISSION,
                description="权限不足，无法执行操作",
                raw_error=error_message,
                context=context,
                severity="high"
            )

        # 磁盘空间
        if any(kw in error_lower for kw in ['no space left', 'disk full', 'enospc', 'quota exceeded']):
            return Obstacle(
                obstacle_type=ObstacleType.DISK_SPACE,
                description="磁盘空间不足",
                raw_error=error_message,
                context=context,
                severity="critical"
            )

        # 网络问题
        if any(kw in error_lower for kw in ['connection refused', 'connection timed out', 'network unreachable', 'etimedout', 'ename or service not known']):
            return Obstacle(
                obstacle_type=ObstacleType.NETWORK,
                description="网络连接问题",
                raw_error=error_message,
                context=context,
                severity="medium"
            )

        # 依赖缺失
        if any(kw in error_lower for kw in ['no module named', 'command not found', 'not found', 'import error']):
            return Obstacle(
                obstacle_type=ObstacleType.DEPENDENCY,
                description="依赖缺失或未安装",
                raw_error=error_message,
                context=context,
                severity="medium"
            )

        # 端口占用
        if any(kw in error_lower for kw in ['address already in use', 'port in use', 'eaddrinuse']):
            return Obstacle(
                obstacle_type=ObstacleType.PORT_CONFLICT,
                description="端口被占用",
                raw_error=error_message,
                context=context,
                severity="medium"
            )

        # 超时
        if any(kw in error_lower for kw in ['timed out', 'timeout', 'deadline exceeded']):
            return Obstacle(
                obstacle_type=ObstacleType.TIMEOUT,
                description="操作超时",
                raw_error=error_message,
                context=context,
                severity="low"
            )

        # 服务问题
        if any(kw in error_lower for kw in ['service failed', 'systemd', 'active: failed']):
            return Obstacle(
                obstacle_type=ObstacleType.SERVICE,
                description="系统服务异常",
                raw_error=error_message,
                context=context,
                severity="high"
            )

        return Obstacle(
            obstacle_type=ObstacleType.UNKNOWN,
            description="未知错误",
            raw_error=error_message,
            context=context,
            severity="medium"
        )

    def get_solutions(self, obstacle: Obstacle) -> List[Solution]:
        """获取解决方案"""
        solutions = []

        type_mapping = {
            ObstacleType.PERMISSION: "permission_denied",
            ObstacleType.DISK_SPACE: "disk_space",
            ObstacleType.NETWORK: "network_connection",
            ObstacleType.DEPENDENCY: "dependency_missing",
            ObstacleType.PORT_CONFLICT: "port_in_use",
            ObstacleType.TIMEOUT: "timeout",
            ObstacleType.SERVICE: "service_failed"
        }

        lib_key = type_mapping.get(obstacle.obstacle_type)
        if lib_key and lib_key in self._solution_library:
            for sol in self._solution_library[lib_key]:
                # 填充变量
                commands = [self._fill_variables(c, obstacle.context) for c in sol["commands"]]
                rollback = [self._fill_variables(c, obstacle.context) for c in sol.get("rollback", [])]

                solutions.append(Solution(
                    solution_id=sol["id"],
                    description=sol["desc"],
                    commands=commands,
                    rollback_commands=rollback,
                    confidence=sol["confidence"],
                    requires_confirmation=sol["requires_confirmation"],
                    requires_sudo=sol["requires_sudo"]
                ))

        return solutions

    def resolve(
        self,
        obstacle: Obstacle,
        solution: Solution,
        dry_run: bool = True
    ) -> ResolutionResult:
        """执行解决"""
        if dry_run:
            return ResolutionResult(
                obstacle=obstacle,
                solution=solution,
                success=True,
                output=f"[Dry Run] 将执行: {solution.description}",
                error=None,
                resolved_at=None
            )

        outputs = []
        errors = []

        for cmd in solution.commands:
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    outputs.append(result.stdout)
                else:
                    errors.append(result.stderr)
            except subprocess.TimeoutExpired:
                errors.append("命令执行超时")
            except Exception as e:
                errors.append(str(e))

        success = len(errors) == 0

        resolution = ResolutionResult(
            obstacle=obstacle,
            solution=solution,
            success=success,
            output='\n'.join(outputs),
            error='\n'.join(errors) if errors else None,
            resolved_at=time.time() if success else None
        )

        self._resolution_history.append(resolution)
        return resolution

    def _fill_variables(self, template: str, context: Dict) -> str:
        """填充变量"""
        replacements = {
            '{command}': context.get('command', ''),
            '{file}': context.get('file', ''),
            '{port}': str(context.get('port', '')),
            '{package}': context.get('package', ''),
            '{service}': context.get('service', ''),
            '{old_port}': str(context.get('old_port', '')),
            '{new_port}': str(context.get('new_port', '')),
            '{config_file}': context.get('config_file', ''),
            '{group}': context.get('group', 'root')
        }

        result = template
        for key, value in replacements.items():
            result = result.replace(key, value)

        return result

    def get_history(self) -> List[ResolutionResult]:
        """获取解决历史"""
        return self._resolution_history


# 全局实例
obstacle_resolver = ObstacleResolver()
