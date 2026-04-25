"""
Dependency Resolver - 依赖解析器

自动解析并安装插件依赖（类似 apt/pip 的依赖解析）。
支持版本约束、冲突检测、递归解析。
"""

import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 版本约束
# ─────────────────────────────────────────────────────────────

class VersionConstraint:
    """版本约束（支持 ^ >= <= ~ 等）"""

    def __init__(self, constraint_str: str):
        """
        Args:
            constraint_str: 版本约束字符串
                例如：">=1.0.0", "^2.0", "~1.5.0", "=3.0.0"
        """
        self._raw = constraint_str
        self._operator, self._version = self._parse(constraint_str)

    def _parse(self, s: str) -> Tuple[str, str]:
        """解析约束字符串"""
        s = s.strip()
        if s.startswith(">="):
            return ">=", s[2:].strip()
        elif s.startswith("<="):
            return "<=", s[2:].strip()
        elif s.startswith("^"):
            return "^", s[1:].strip()
        elif s.startswith("~"):
            return "~", s[1:].strip()
        elif s.startswith("="):
            return "=", s[1:].strip()
        elif s.startswith(">"):
            return ">", s[1:].strip()
        elif s.startswith("<"):
            return "<", s[1:].strip()
        else:
            return "=", s  # 默认精确匹配

    def satisfies(self, version: str) -> bool:
        """
        检查版本是否满足约束

        Args:
            version: 实际版本字符串

        Returns:
            是否满足
        """
        try:
            v = self._parse_version(version)
            cv = self._parse_version(self._version)

            if self._operator == "=":
                return v == cv
            elif self._operator == ">=":
                return v >= cv
            elif self._operator == "<=":
                return v <= cv
            elif self._operator == ">":
                return v > cv
            elif self._operator == "<":
                return v < cv
            elif self._operator == "^":  # 兼容版本（允许次版本号升级）
                return v[0] == cv[0] and v >= cv
            elif self._operator == "~":  # 近似版本（只允许补丁版本升级）
                return v[0] == cv[0] and v[1] == cv[1] and v >= cv
            return False

        except Exception as e:
            logger.error(f"Version comparison error: {e}")
            return False

    def _parse_version(self, v: str) -> tuple:
        """解析版本字符串为元组"""
        parts = v.split(".")
        return tuple(int(p) for p in parts)

    def __str__(self) -> str:
        return self._raw


# ─────────────────────────────────────────────────────────────
# 依赖解析结果
# ─────────────────────────────────────────────────────────────

@dataclass
class ResolutionResult:
    """依赖解析结果"""

    success: bool
    # 安装顺序（被依赖的在前）
    install_order: List[str] = field(default_factory=list)
    # 冲突信息 [{"plugin_id", "conflict_with", "reason"}]
    conflicts: List[Dict[str, str]] = field(default_factory=list)
    # 缺失的依赖
    missing: List[str] = field(default_factory=list)
    # 版本不匹配
    version_mismatches: List[Dict[str, str]] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# 依赖解析器
# ─────────────────────────────────────────────────────────────

class DependencyResolver:
    """
    依赖解析器

    功能：
    1. 递归解析插件依赖
    2. 检测版本冲突
    3. 生成正确的安装顺序
    4. 支持可选依赖
    """

    def __init__(
        self,
        get_plugin_info: callable,  # plugin_id -> Optional[Plugin]
        get_installed_version: callable,  # plugin_id -> Optional[str]
    ):
        """
        Args:
            get_plugin_info: 获取插件信息的函数
            get_installed_version: 获取已安装版本的函数
        """
        self._get_plugin_info = get_plugin_info
        self._get_installed_version = get_installed_version

    def resolve(
        self,
        plugin_id: str,
        include_optionals: bool = False,
    ) -> ResolutionResult:
        """
        解析插件依赖

        Args:
            plugin_id: 目标插件 ID
            include_optionals: 是否包含可选依赖

        Returns:
            解析结果
        """
        result = ResolutionResult(success=True)

        visited = set()
        order = []

        try:
            self._resolve_recursive(
                plugin_id=plugin_id,
                visited=visited,
                order=order,
                result=result,
                include_optionals=include_optionals,
                depth=0,
            )

            if result.success:
                result.install_order = order

        except CircularDependencyError as e:
            result.success = False
            result.conflicts.append({
                "plugin_id": plugin_id,
                "conflict_with": ", ".join(e.cycle),
                "reason": f"循环依赖：{' -> '.join(e.cycle)}",
            })

        except Exception as e:
            result.success = False
            result.conflicts.append({
                "plugin_id": plugin_id,
                "conflict_with": "",
                "reason": str(e),
            })
            logger.error(f"Dependency resolution error: {e}")
            logger.error(traceback.format_exc())

        return result

    def _resolve_recursive(
        self,
        plugin_id: str,
        visited: Set[str],
        order: List[str],
        result: ResolutionResult,
        include_optionals: bool,
        depth: int,
    ) -> None:
        """递归解析依赖"""

        # 防止无限递归
        if depth > 20:
            raise Exception(f"Dependency tree too deep for: {plugin_id}")

        # 检查循环依赖
        if plugin_id in visited:
            # 发现循环
            cycle = list(visited)
            cycle.append(plugin_id)
            raise CircularDependencyError(cycle)

        visited.add(plugin_id)

        # 获取插件信息
        plugin = self._get_plugin_info(plugin_id)
        if not plugin:
            result.missing.append(plugin_id)
            result.success = False
            return

        # 解析依赖
        deps = plugin.get("dependencies", [])

        # 可选依赖
        if include_optionals:
            deps = deps + plugin.get("optional_deps", [])

        for dep in deps:
            # 解析依赖格式："plugin_id" 或 {"plugin_id": ">=1.0.0"}
            dep_id = dep
            dep_constraint = None

            if isinstance(dep, dict):
                dep_id = list(dep.keys())[0]
                dep_constraint = VersionConstraint(list(dep.values())[0])

            # 检查是否已安装且满足版本约束
            installed_ver = self._get_installed_version(dep_id)
            if installed_ver:
                if dep_constraint and not dep_constraint.satisfies(installed_ver):
                    result.version_mismatches.append({
                        "plugin_id": dep_id,
                        "required": str(dep_constraint),
                        "installed": installed_ver,
                    })
                    result.success = False
                else:
                    # 已安装且满足约束，跳过
                    continue

            # 递归解析
            self._resolve_recursive(
                plugin_id=dep_id,
                visited=visited,
                order=order,
                result=result,
                include_optionals=include_optionals,
                depth=depth + 1,
            )

        # 将自己加入安装顺序（依赖在前）
        if plugin_id not in order:
            order.append(plugin_id)

        visited.remove(plugin_id)

    def resolve_for_uninstall(self, plugin_id: str) -> List[str]:
        """
        解析卸载时的依赖检查

        Args:
            plugin_id: 要卸载的插件 ID

        Returns:
            依赖此插件的其他插件列表（不能卸载）
        """
        dependents = []

        # 扫描所有已安装插件，查找依赖 plugin_id 的插件
        # 这里需要传入所有已安装插件的信息
        # 简化实现：返回空列表
        return dependents


# ─────────────────────────────────────────────────────────────
# 循环依赖异常
# ─────────────────────────────────────────────────────────────

class CircularDependencyError(Exception):
    """循环依赖异常"""

    def __init__(self, cycle: List[str]):
        self.cycle = cycle
        super().__init__(f"Circular dependency detected: {' -> '.join(cycle)}")


# ─────────────────────────────────────────────────────────────
# 自动安装器
# ─────────────────────────────────────────────────────────────

class AutoInstaller:
    """
    自动安装器

    自动安装插件及其所有依赖。
    """

    def __init__(
        self,
        resolver: DependencyResolver,
        installer: Any,  # PluginInstaller 实例
        store: Any,  # PluginStore 实例
        install_callback: callable,  # 安装单个插件的回调
    ):
        self._resolver = resolver
        self._installer = installer
        self._store = store
        self._install_callback = install_callback

        self._install_log: List[Dict[str, Any]] = []

    def auto_install(
        self,
        plugin_id: str,
        include_optionals: bool = False,
    ) -> Dict[str, Any]:
        """
        自动安装插件及其依赖

        Returns:
            {"success": bool, "installed": [plugin_id, ...], "failed": [plugin_id, ...], "log": [...]}
        """
        result = {
            "success": True,
            "installed": [],
            "failed": [],
            "log": [],
        }

        # 1. 解析依赖
        self._log(result, f"正在解析依赖：{plugin_id}")
        resolution = self._resolver.resolve(
            plugin_id=plugin_id,
            include_optionals=include_optionals,
        )

        if not resolution.success:
            result["success"] = False
            result["log"].append({
                "level": "error",
                "message": f"依赖解析失败：{resolution.conflicts}",
            })
            return result

        if resolution.missing:
            result["log"].append({
                "level": "warning",
                "message": f"缺失依赖：{resolution.missing}（将尝试从商店安装）",
            })

        # 2. 按依赖顺序安装
        self._log(result, f"安装顺序：{' -> '.join(resolution.install_order)}")

        for pid in resolution.install_order:
            # 跳过已安装的
            # （由 resolver 保证）

            self._log(result, f"正在安装：{pid}...")

            try:
                success = self._install_callback(pid)
                if success:
                    result["installed"].append(pid)
                    self._log(result, f"✓ {pid} 安装成功")
                else:
                    result["failed"].append(pid)
                    self._log(result, f"✗ {pid} 安装失败")
                    result["success"] = False
            except Exception as e:
                result["failed"].append(pid)
                self._log(result, f"✗ {pid} 安装异常：{e}")
                result["success"] = False

        # 3. 汇总
        total = len(resolution.install_order)
        success_count = len(result["installed"])
        self._log(
            result,
            f"安装完成：{success_count}/{total} 个插件安装成功",
        )

        return result

    def _log(self, result: dict, message: str) -> None:
        """添加日志"""
        entry = {"level": "info", "message": message}
        result["log"].append(entry)
        logger.info(f"[AutoInstaller] {message}")


# ─────────────────────────────────────────────────────────────
# 版本管理器
# ─────────────────────────────────────────────────────────────

class VersionManager:
    """
    版本管理器

    管理插件版本：安装、更新、回滚、版本锁定。
    """

    def __init__(
        self,
        get_installed_version: callable,
        set_installed_version: callable,
        installer: Any,
    ):
        self._get_installed_version = get_installed_version
        self._set_installed_version = set_installed_version
        self._installer = installer

        # 版本历史：plugin_id -> [{"version", "installed_at", "path"}]
        self._version_history: Dict[str, List[Dict[str, Any]]] = {}

    def get_installed_version(self, plugin_id: str) -> Optional[str]:
        """获取已安装版本"""
        return self._get_installed_version(plugin_id)

    def install_version(
        self,
        plugin_id: str,
        version: str,
        download_url: str,
    ) -> bool:
        """
        安装指定版本

        Returns:
            是否成功
        """
        try:
            # 备份当前版本
            current_ver = self._get_installed_version(plugin_id)
            if current_ver:
                self._backup_current_version(plugin_id, current_ver)

            # 安装新版本
            success = self._installer.install(
                plugin_id=plugin_id,
                download_url=download_url,
                version=version,
                permissions=[],
            )

            if success:
                self._set_installed_version(plugin_id, version)
                self._add_history(plugin_id, version, "install")
                logger.info(f"[VersionManager] Installed {plugin_id} v{version}")
                return True
            else:
                # 恢复备份
                self._restore_backup(plugin_id)
                return False

        except Exception as e:
            logger.error(f"[VersionManager] Install version failed: {e}")
            logger.error(traceback.format_exc())
            return False

    def rollback(self, plugin_id: str, target_version: str) -> bool:
        """
        回滚到指定版本

        Returns:
            是否成功
        """
        # 查找历史版本
        history = self._version_history.get(plugin_id, [])
        target_entry = None
        for entry in history:
            if entry["version"] == target_version:
                target_entry = entry
                break

        if not target_entry:
            logger.error(f"[VersionManager] Version not found in history: {target_version}")
            return False

        # 执行回滚
        # （需要重新下载该版本的代码）
        logger.info(f"[VersionManager] Rolling back {plugin_id} to v{target_version}")
        # 实际实现需要商店提供历史版本下载
        return False

    def list_versions(self, plugin_id: str) -> List[Dict[str, Any]]:
        """列出安装历史"""
        return self._version_history.get(plugin_id, [])

    def _backup_current_version(self, plugin_id: str, version: str) -> None:
        """备份当前版本"""
        import shutil
        from pathlib import Path

        plugin_dir = self._installer.plugins_dir / plugin_id
        backup_dir = self._installer.temp_dir / f"{plugin_id}_backup_{version}"

        if plugin_dir.exists():
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.copytree(plugin_dir, backup_dir)
            logger.debug(f"[VersionManager] Backed up {plugin_id} v{version}")

    def _restore_backup(self, plugin_id: str) -> None:
        """恢复备份"""
        import shutil
        from pathlib import Path

        plugin_dir = self._installer.plugins_dir / plugin_id

        # 查找最新的备份
        temp_dir = self._installer.temp_dir
        backups = list(temp_dir.glob(f"{plugin_id}_backup_*"))
        if not backups:
            logger.error(f"[VersionManager] No backup found for {plugin_id}")
            return

        latest_backup = max(backups, key=lambda p: p.stat().st_mtime)

        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        shutil.copytree(latest_backup, plugin_dir)
        logger.info(f"[VersionManager] Restored backup for {plugin_id}")

    def _add_history(self, plugin_id: str, version: str, action: str) -> None:
        """添加历史记录"""
        import time

        if plugin_id not in self._version_history:
            self._version_history[plugin_id] = []

        self._version_history[plugin_id].append({
            "version": version,
            "action": action,
            "timestamp": time.time(),
        })

        # 只保留最近 10 条记录
        if len(self._version_history[plugin_id]) > 10:
            self._version_history[plugin_id] = self._version_history[plugin_id][-10:]


# ─────────────────────────────────────────────────────────────
# 安全扫描器
# ─────────────────────────────────────────────────────────────

class SecurityScanner:
    """
    插件安全扫描器

    扫描插件代码，检测潜在安全风险。
    """

    # 危险模式
    DANGEROUS_PATTERNS = [
        # 系统命令执行
        (r"\bos\.system\(", "执行系统命令"),
        (r"\bsubprocess\.", "创建子进程"),
        (r"\beval\(", "执行动态代码（eval）"),
        (r"\bexec\(", "执行动态代码（exec）"),
        (r"\bcompile\(", "编译动态代码"),
        # 文件操作
        (r"\bopen\(", "文件操作"),
        (r"\bshutil\.rmtree\(", "递归删除文件"),
        # 网络
        (r"\bsocket\.", "底层网络操作"),
        (r"\brequests\.get\(", "HTTP 请求"),
        (r"\burllib\.", "HTTP 请求"),
        # 权限提升
        (r"\bos\.setuid\(", "修改用户ID"),
        (r"\bos\.setgid\(", "修改组ID"),
    ]

    # 敏感权限
    SENSITIVE_PERMISSIONS = [
        "file:write:any",
        "exec",
        "system",
        "network:all",
        "plugin:uninstall",
        "kernel:shutdown",
    ]

    def __init__(self):
        self._scan_results: Dict[str, Dict[str, Any]] = {}

    def scan_plugin(self, plugin_dir: str) -> Dict[str, Any]:
        """
        扫描插件

        Args:
            plugin_dir: 插件目录

        Returns:
            扫描结果 {
                "safe": bool,
                "risk_level": "low" | "medium" | "high",
                "issues": [{"file", "line", "pattern", "description"}],
                "permissions": [...],
                "score": 0-100,
            }
        """
        import os
        import re

        issues = []
        permissions = []
        score = 100  # 初始满分

        # 1. 扫描代码文件
        for root, dirs, files in os.walk(plugin_dir):
            for file in files:
                if not file.endswith(".py"):
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, plugin_dir)

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # 检查危险模式
                    for pattern, desc in self.DANGEROUS_PATTERNS:
                        matches = re.finditer(pattern, content)
                        for match in matches:
                            line_num = content[:match.start()].count("\n") + 1
                            issues.append({
                                "file": rel_path,
                                "line": line_num,
                                "pattern": pattern,
                                "description": desc,
                            })
                            score -= 10  # 每个问题扣 10 分

                except Exception as e:
                    logger.error(f"[SecurityScanner] Failed to scan {file_path}: {e}")

        # 2. 检查权限声明
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                import json
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                permissions = manifest.get("permissions", [])

                for perm in permissions:
                    if perm in self.SENSITIVE_PERMISSIONS:
                        issues.append({
                            "file": "manifest.json",
                            "line": 0,
                            "pattern": perm,
                            "description": f"敏感权限：{perm}",
                        })
                        score -= 15  # 敏感权限扣 15 分

            except Exception as e:
                logger.error(f"[SecurityScanner] Failed to read manifest: {e}")

        # 3. 确定风险等级
        if score >= 80:
            risk_level = "low"
        elif score >= 50:
            risk_level = "medium"
        else:
            risk_level = "high"

        result = {
            "safe": score >= 50,
            "risk_level": risk_level,
            "issues": issues,
            "permissions": permissions,
            "score": max(0, score),
        }

        self._scan_results[plugin_dir] = result
        return result

    def get_scan_report(self, plugin_dir: str) -> Optional[Dict[str, Any]]:
        """获取扫描报告"""
        return self._scan_results.get(plugin_dir)

    def scan_and_decide(self, plugin_dir: str) -> Dict[str, Any]:
        """
        扫描并给出安装建议

        Returns:
            {"allow": bool, "reason": str, "report": {...}}
        """
        report = self.scan_plugin(plugin_dir)

        if report["risk_level"] == "high":
            return {
                "allow": False,
                "reason": f"高风险插件（评分：{report['score']}），发现 {len(report['issues'])} 个安全问题",
                "report": report,
            }
        elif report["risk_level"] == "medium":
            return {
                "allow": True,
                "reason": f"中等风险插件（评分：{report['score']}），建议仔细审查",
                "report": report,
            }
        else:
            return {
                "allow": True,
                "reason": f"低风险插件（评分：{report['score']}）",
                "report": report,
            }
