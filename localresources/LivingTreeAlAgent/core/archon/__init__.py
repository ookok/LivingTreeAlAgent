"""
Archon 系统级智能体模块
基于 coleam0O/Archon 思想：让 AI 具备系统级操作权限

功能：
- 系统命令执行 (git/docker/npm)
- 文件读写操作
- 进程管理
- 安全沙箱隔离
"""

import os
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class PermissionLevel(Enum):
    """权限级别"""
    NONE = 0      # 无权限
    READ = 1      # 只读
    WRITE = 2     # 读写
    EXECUTE = 3   # 可执行命令


@dataclass
class WorkspaceBounds:
    """工作空间边界（安全隔离）"""
    root: Path
    blocked_paths: List[Path] = field(default_factory=list)

    def is_within_bounds(self, path: Path) -> bool:
        """检查路径是否在边界内"""
        try:
            resolved = path.resolve()
            root_resolved = self.root.resolve()
            if not str(resolved).startswith(str(root_resolved)):
                return False
            for blocked in self.blocked_paths:
                if str(resolved).startswith(str(blocked.resolve())):
                    return False
            return True
        except Exception:
            return False


@dataclass
class SystemCapability:
    """系统能力定义"""
    name: str
    command_template: str
    description: str
    permission: PermissionLevel = PermissionLevel.EXECUTE
    requires_confirmation: bool = False


class ArchonCore:
    """Archon 系统级智能体核心"""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path("./workspace")
        self.workspace_root.mkdir(parents=True, exist_ok=True)

        self.bounds = WorkspaceBounds(
            root=self.workspace_root,
            blocked_paths=[
                Path.home() / ".ssh",
                Path.home() / ".aws",
                Path("/etc"),
                Path("/root"),
            ]
        )
        self.capabilities = self._init_capabilities()
        self.permission_map: Dict[str, PermissionLevel] = {}

    def _init_capabilities(self) -> Dict[str, SystemCapability]:
        """初始化预定义能力"""
        return {
            "git_commit": SystemCapability(
                name="git_commit",
                command_template="git add -A && git commit -m '{message}'",
                description="提交代码更改",
                permission=PermissionLevel.EXECUTE,
                requires_confirmation=True
            ),
            "git_push": SystemCapability(
                name="git_push",
                command_template="git push",
                description="推送代码到远程",
                permission=PermissionLevel.EXECUTE
            ),
            "docker_build": SystemCapability(
                name="docker_build",
                command_template="docker build -t {image_name} {dockerfile_path}",
                description="构建 Docker 镜像",
                permission=PermissionLevel.EXECUTE,
                requires_confirmation=True
            ),
            "npm_install": SystemCapability(
                name="npm_install",
                command_template="npm install {package_name}",
                description="安装 npm 包",
                permission=PermissionLevel.EXECUTE
            ),
            "pip_install": SystemCapability(
                name="pip_install",
                command_template="pip install {package_name}",
                description="安装 Python 包",
                permission=PermissionLevel.EXECUTE
            ),
            "file_read": SystemCapability(
                name="file_read",
                command_template="read:{path}",
                description="读取文件内容",
                permission=PermissionLevel.READ
            ),
            "file_write": SystemCapability(
                name="file_write",
                command_template="write:{path}:{content}",
                description="写入文件内容",
                permission=PermissionLevel.WRITE,
                requires_confirmation=True
            ),
            "dir_list": SystemCapability(
                name="dir_list",
                command_template="list:{path}",
                description="列出目录内容",
                permission=PermissionLevel.READ
            ),
        }

    def set_permission(self, capability_name: str, level: PermissionLevel):
        """设置能力权限"""
        self.permission_map[capability_name] = level

    async def execute(
        self,
        capability: str,
        params: Dict[str, Any],
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """执行系统操作"""
        if capability not in self.capabilities:
            return {"success": False, "error": f"Unknown capability: {capability}"}

        cap = self.capabilities[capability]
        user_level = self.permission_map.get(capability, PermissionLevel.NONE)

        if user_level.value < cap.permission.value:
            return {"success": False, "error": f"Permission denied for {capability}"}

        # 处理文件操作
        if capability.startswith("file_") or capability == "dir_list":
            return await self._handle_file_operation(capability, params, dry_run)

        # 构建命令
        command = cap.command_template
        for key, value in params.items():
            command = command.replace(f"{{{key}}}", str(value))

        if dry_run:
            return {"success": True, "preview": True, "command": command}

        try:
            result = await self._run_command(command)
            return {
                "success": result["returncode"] == 0,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "command": command
            }
        except Exception as e:
            return {"success": False, "error": str(e), "command": command}

    async def _handle_file_operation(self, capability: str, params: Dict, dry_run: bool) -> Dict:
        """处理文件操作"""
        if capability == "file_read":
            file_path = Path(params.get("path", ""))
            if not self.bounds.is_within_bounds(file_path):
                return {"success": False, "error": "Path outside workspace bounds"}
            if not file_path.exists():
                return {"success": False, "error": "File not found"}
            content = file_path.read_text(encoding="utf-8")
            return {"success": True, "content": content, "path": str(file_path)}

        elif capability == "file_write":
            file_path = Path(params.get("path", ""))
            if not self.bounds.is_within_bounds(file_path):
                return {"success": False, "error": "Path outside workspace bounds"}
            if dry_run:
                return {"success": True, "preview": True, "message": f"Would write to {file_path}"}
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(params.get("content", ""), encoding="utf-8")
            return {"success": True, "path": str(file_path)}

        elif capability == "dir_list":
            dir_path = Path(params.get("path", "."))
            if not self.bounds.is_within_bounds(dir_path):
                return {"success": False, "error": "Path outside workspace bounds"}
            if not dir_path.exists():
                return {"success": False, "error": "Directory not found"}
            items = [
                {"Name": p.name, "type": "dir" if p.is_dir() else "file"}
                for p in dir_path.iterdir()
            ]
            return {"success": True, "items": items}

        return {"success": False, "error": "Unknown operation"}

    async def _run_command(self, command: str) -> Dict[str, Any]:
        """运行系统命令"""
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        return {
            "returncode": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace")
        }


class ArchonAgent:
    """Archon Agent - 系统级智能体封装"""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.core = ArchonCore(workspace_root)
        self.execution_history: List[Dict] = []

    async def execute_workflow(self, steps: List[Dict], confirm_each: bool = False) -> List[Dict]:
        """执行工作流步骤"""
        results = []
        for i, step in enumerate(steps):
            capability = step.get("capability")
            params = step.get("params", {})
            result = await self.core.execute(capability, params)
            results.append(result)
            self.execution_history.append({"step": i, "capability": capability, "result": result})
            if not result.get("success", False):
                break
        return results

    async def git_workflow(self, commit_message: str) -> Dict[str, Any]:
        """执行 Git 标准工作流"""
        steps = [
            {"capability": "git_commit", "params": {"message": commit_message}},
            {"capability": "git_push", "params": {}}
        ]
        results = await self.execute_workflow(steps)
        return {"success": all(r.get("success", False) for r in results), "results": results}


_archon_instance: Optional[ArchonAgent] = None


def get_archon(workspace_root: Optional[Path] = None) -> ArchonAgent:
    """获取 Archon 单例"""
    global _archon_instance
    if _archon_instance is None:
        _archon_instance = ArchonAgent(workspace_root)
    return _archon_instance