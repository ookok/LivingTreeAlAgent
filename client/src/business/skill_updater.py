"""
Skill/专家角色自动更新器
===========================

功能：
1. 检查本地 skills 目录是否为 Git 仓库
2. 如果是，执行 git pull 获取最新更新
3. 支持定期检查和手动触发
4. 记录更新日志

使用场景：
- 远程仓库更新了 skill/专家角色内容（如法规更新、新工具发布）
- 本地自动同步最新版本
- 适应时代变化（法规更新、技术要求变化）
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class SkillUpdater:
    """
    Skill/专家角色自动更新器
    
    设计原则：
    1. 只更新 Git 仓库（用户明确 clone 的）
    2. 不自动更新手动创建的 skill（避免覆盖用户修改）
    3. 更新前检查网络连接
    4. 更新后通知用户（通过 AgentRegistry）
    """
    
    def __init__(self):
        self._skills_dirs = self._find_skills_dirs()
        self._update_log: List[Dict] = []
        self._update_details: List[Dict] = []  # 存储更新详细信息
        
    def _find_skills_dirs(self) -> List[Path]:
        """查找所有 skills 目录"""
        dirs = []
        
        # 用户级 skills 目录
        user_skills = Path.home() / ".workbuddy" / "skills"
        if user_skills.exists():
            dirs.append(user_skills)
        
        # 项目内置 skills 目录
        project_skills = Path("d:/mhzyapp/LivingTreeAlAgent/.livingtree/skills")
        if project_skills.exists():
            dirs.append(project_skills)
            
        return dirs
    
    def check_updates(self) -> List[Tuple[Path, bool, str]]:
        """
        检查所有 skills 目录是否有更新
        
        Returns:
            [(目录路径, 是否有更新, 状态信息), ...]
        """
        results = []
        
        for skills_dir in self._skills_dirs:
            # 检查是否为 Git 仓库
            git_dir = skills_dir / ".git"
            if not git_dir.exists():
                results.append((skills_dir, False, "非 Git 仓库，跳过"))
                continue
            
            # 执行 git fetch 检查远程更新
            try:
                import subprocess
                
                # 1. git fetch（获取远程最新状态）
                fetch_result = subprocess.run(
                    ["git", "fetch", "--quiet"],
                    cwd=str(skills_dir),
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if fetch_result.returncode != 0:
                    results.append((skills_dir, False, f"git fetch 失败: {fetch_result.stderr}"))
                    continue
                
                # 2. 检查本地和远程是否有差异
                # 比较 HEAD 和 origin/HEAD
                local_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(skills_dir),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                remote_result = subprocess.run(
                    ["git", "rev-parse", "origin/HEAD"],
                    cwd=str(skills_dir),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if local_result.returncode == 0 and remote_result.returncode == 0:
                    local_hash = local_result.stdout.strip()
                    remote_hash = remote_result.stdout.strip()
                    
                    if local_hash == remote_hash:
                        results.append((skills_dir, False, "已是最新版本"))
                    else:
                        results.append((skills_dir, True, "有可用更新"))
                else:
                    results.append((skills_dir, False, "无法比较本地和远程版本"))
                    
            except subprocess.TimeoutExpired:
                results.append((skills_dir, False, "检查超时（网络问题？）"))
            except Exception as e:
                results.append((skills_dir, False, f"检查失败: {str(e)}"))
        
        return results
    
    def update_all(self, progress_callback=None) -> List[Dict]:
        """
        更新所有有更新的 skills 目录
        
        Args:
            progress_callback: 进度回调函数，接收 (current, total, message) 参数
            
        Returns:
            更新结果列表 [{"dir": 路径, "success": 是否成功, "message": 信息, "files": [{"file": 文件名, "status": 状态}]}, ...]
        """
        check_results = self.check_updates()
        update_results = []
        
        # 计算需要更新的目录数量
        total = sum(1 for _, has_update, _ in check_results if has_update)
        current = 0
        
        for skills_dir, has_update, status in check_results:
            if not has_update:
                update_results.append({
                    "dir": str(skills_dir),
                    "success": True,
                    "updated": False,
                    "message": status
                })
                continue
            
            # 更新进度
            current += 1
            if progress_callback:
                progress_callback(current, total, f"正在更新: {skills_dir.name}")
            
            # 执行 git pull
            try:
                import subprocess
                
                pull_result = subprocess.run(
                    ["git", "pull"],
                    cwd=str(skills_dir),
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if pull_result.returncode == 0:
                    message = pull_result.stdout.strip() or "更新成功"
                    
                    # 获取更新的文件列表
                    changed_files = self._get_changed_files(skills_dir)
                    
                    update_results.append({
                        "dir": str(skills_dir),
                        "success": True,
                        "updated": True,
                        "message": message,
                        "files": changed_files  # 添加更新的文件列表
                    })
                    
                    # 记录更新日志
                    self._log_update(skills_dir, message)
                    
                    # 记录更新详细信息
                    self._update_details.append({
                        "timestamp": datetime.now().isoformat(),
                        "dir": str(skills_dir),
                        "files": changed_files
                    })
                    
                    logger.info(f"[SkillUpdater] 更新成功: {skills_dir} - {message}")
                else:
                    update_results.append({
                        "dir": str(skills_dir),
                        "success": False,
                        "updated": False,
                        "message": pull_result.stderr.strip()
                    })
                    logger.error(f"[SkillUpdater] 更新失败: {skills_dir} - {pull_result.stderr}")
                    
            except subprocess.TimeoutExpired:
                update_results.append({
                    "dir": str(skills_dir),
                    "success": False,
                    "updated": False,
                    "message": "更新超时"
                })
            except Exception as e:
                update_results.append({
                    "dir": str(skills_dir),
                    "success": False,
                    "updated": False,
                    "message": str(e)
                })
        
        # 更新完成
        if progress_callback:
            progress_callback(total, total, "更新完成")
        
        return update_results
    
    def update_skill(self, skill_name: str) -> Dict:
        """
        更新指定的 skill/专家角色
        
        Args:
            skill_name: 技能或专家角色名称
            
        Returns:
            {"success": bool, "message": str}
        """
        for skills_dir in self._skills_dirs:
            skill_path = skills_dir / skill_name
            
            if not skill_path.exists():
                continue
            
            # 找到 skill 目录，检查它是否在 Git 仓库中
            # 向上查找 .git 目录
            current = skill_path.resolve()
            git_dir = None
            
            while current != current.parent:
                if (current / ".git").exists():
                    git_dir = current / ".git"
                    break
                current = current.parent
            
            if git_dir is None:
                return {
                    "success": False,
                    "message": f"{skill_name} 不在 Git 仓库中，无法自动更新"
                }
            
            # 执行 git pull（在 Git 仓库根目录）
            try:
                import subprocess
                
                repo_root = git_dir.parent
                
                pull_result = subprocess.run(
                    ["git", "pull"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if pull_result.returncode == 0:
                    message = pull_result.stdout.strip() or "更新成功"
                    self._log_update(repo_root, f"{skill_name}: {message}")
                    return {"success": True, "message": message}
                else:
                    return {"success": False, "message": pull_result.stderr.strip()}
                    
            except Exception as e:
                return {"success": False, "message": str(e)}
        
        return {"success": False, "message": f"找不到 skill: {skill_name}"}
    
    def _log_update(self, directory: Path, message: str):
        """记录更新日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "directory": str(directory),
            "message": message
        }
        
        self._update_log.append(log_entry)
        
        # 保存到日志文件
        log_file = Path.home() / ".workbuddy" / "skill_update_log.json"
        try:
            # 读取现有日志
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    all_logs = json.load(f)
            else:
                all_logs = []
            
            # 添加新日志
            all_logs.append(log_entry)
            
            # 只保留最近 100 条日志
            all_logs = all_logs[-100:]
            
            # 保存
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(all_logs, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"[SkillUpdater] 保存更新日志失败: {e}")
    
    def get_update_log(self, limit: int = 20) -> List[Dict]:
        """获取最近更新日志"""
        log_file = Path.home() / ".workbuddy" / "skill_update_log.json"
        
        if not log_file.exists():
            return []
        
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                all_logs = json.load(f)
                return all_logs[-limit:]
        except Exception as e:
            logger.error(f"[SkillUpdater] 读取更新日志失败: {e}")
            return []
    
    def get_update_details(self) -> List[Dict]:
        """
        获取最近更新详细信息（哪些文件被更新、更新内容）
        
        Returns:
            更新详细信息列表 [{"dir": 路径, "files": [{"file": 文件名, "status": 状态}], ...}]
        """
        return self._update_details
    
    def _get_changed_files(self, repo_root: Path) -> List[Dict]:
        """
        获取最近一次 pull 更新的文件列表
        
        Args:
            repo_root: Git 仓库根目录
            
        Returns:
            文件变更列表 [{"file": 文件名, "status": 状态}, ...]
            状态：Added, Modified, Deleted, Renamed
        """
        try:
            import subprocess
            
            # 获取最近一次 pull 的合并基础
            result = subprocess.run(
                ["git", "log", "-1", "--name-status", "--pretty=format:"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return []
            
            # 解析输出
            changed_files = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                
                parts = line.split("\t")
                if len(parts) >= 2:
                    status = parts[0].strip()
                    file_path = parts[1].strip()
                    changed_files.append({
                        "file": file_path,
                        "status": status  # A=Added, M=Modified, D=Deleted, R=Renamed
                    })
            
            return changed_files
            
        except Exception as e:
            logger.error(f"[SkillUpdater] 获取变更文件失败: {e}")
            return []


# 全局实例
_updater: Optional[SkillUpdater] = None


def get_skill_updater() -> SkillUpdater:
    """获取 SkillUpdater 单例"""
    global _updater
    if _updater is None:
        _updater = SkillUpdater()
    return _updater


if __name__ == "__main__":
    # 测试
    updater = get_skill_updater()
    
    print("=== 检查更新 ===")
    check_results = updater.check_updates()
    for directory, has_update, status in check_results:
        print(f"{directory}: {status}")
    
    print("\n=== 执行更新 ===")
    update_results = updater.update_all()
    for result in update_results:
        status = "✅" if result["success"] else "❌"
        updated = "（已更新）" if result.get("updated") else ""
        print(f"{status} {result['dir']} {updated}: {result['message']}")
    
    print("\n=== 更新日志 ===")
    logs = updater.get_update_log(limit=5)
    for log in logs:
        print(f"{log['timestamp']}: {log['directory']} - {log['message']}")
