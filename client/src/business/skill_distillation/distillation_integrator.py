"""
DistillationIntegrator - 蒸馏技能集成器

集成外部蒸馏技能到 LivingTreeAlAgent 系统。
提供安装、更新、注册等完整功能。
"""

from typing import Dict, Any, Optional, List
from loguru import logger
import os
import subprocess
import shutil

from .distillation_config import SkillSource, DistillationConfig, DEFAULT_SKILL_SOURCES
from .skill_finder import SkillFinder
from .skill_converter import SkillConverter
from business.skill_evolution.skill_registry import SkillRegistry, PermissionLevel


class DistillationIntegrator:
    """蒸馏技能集成器"""

    def __init__(self):
        self._logger = logger.bind(component="DistillationIntegrator")
        self._finder = SkillFinder()
        self._converter = SkillConverter()
        self._skill_registry = SkillRegistry()
        self._install_dir = self._get_install_dir()

    def _get_install_dir(self) -> str:
        """获取安装目录"""
        install_dir = os.path.expanduser("~/LivingTreeAI/distilled_skills")
        os.makedirs(install_dir, exist_ok=True)
        return install_dir

    def install_skill(self, name: str) -> Dict[str, Any]:
        """
        安装技能
        
        Args:
            name: 技能名称
            
        Returns:
            安装结果
        """
        source = self._finder.get_source_info(name)
        if not source:
            return {"success": False, "message": f"技能源不存在: {name}"}

        if source.get("installed"):
            return {"success": False, "message": f"技能已安装: {name}"}

        source_info = self._finder._config.get_source(name)
        if not source_info:
            return {"success": False, "message": f"技能源配置不存在: {name}"}

        try:
            if source_info.type == "github":
                result = self._clone_github_repo(source_info.url, name)
            elif source_info.type == "local":
                result = self._copy_local_skill(source_info.url, name)
            else:
                return {"success": False, "message": f"不支持的源类型: {source_info.type}"}

            if result["success"]:
                # 尝试转换和注册
                self._convert_and_register_skill(name)
                self._logger.info(f"安装技能成功: {name}")

            return result

        except Exception as e:
            self._logger.error(f"安装技能失败 {name}: {e}")
            return {"success": False, "message": str(e)}

    def _clone_github_repo(self, url: str, name: str) -> Dict[str, Any]:
        """
        克隆 GitHub 仓库
        
        Args:
            url: GitHub 仓库 URL
            name: 技能名称
            
        Returns:
            克隆结果
        """
        install_path = os.path.join(self._install_dir, name)
        
        try:
            self._logger.info(f"克隆仓库: {url} -> {install_path}")
            
            result = subprocess.run(
                ["git", "clone", url, install_path],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                return {"success": True, "message": "克隆成功", "path": install_path}
            else:
                return {"success": False, "message": f"克隆失败: {result.stderr}"}
                
        except subprocess.TimeoutExpired:
            return {"success": False, "message": "克隆超时"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _copy_local_skill(self, path: str, name: str) -> Dict[str, Any]:
        """
        复制本地技能
        
        Args:
            path: 本地路径
            name: 技能名称
            
        Returns:
            复制结果
        """
        install_path = os.path.join(self._install_dir, name)
        
        try:
            if os.path.isdir(path):
                shutil.copytree(path, install_path)
            else:
                os.makedirs(install_path, exist_ok=True)
                shutil.copy(path, install_path)
            
            return {"success": True, "message": "复制成功", "path": install_path}
            
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _convert_and_register_skill(self, name: str):
        """
        转换并注册技能
        
        Args:
            name: 技能名称
        """
        install_path = os.path.join(self._install_dir, name)
        
        # 查找技能文件
        skill_files = []
        for root, _, files in os.walk(install_path):
            for filename in files:
                if filename.endswith(('.json', '.yaml', '.yml', '.md', '.py')):
                    skill_files.append(os.path.join(root, filename))

        # 转换并注册
        for filepath in skill_files:
            try:
                tool_instance = self._converter.convert_and_register(filepath)
                if tool_instance:
                    # 在技能注册中心也注册
                    self._skill_registry.register_skill(
                        skill_id=tool_instance.name,
                        name=tool_instance.name.replace("_", " ").title(),
                        description=tool_instance.description,
                        category=tool_instance.category,
                        permission_level=PermissionLevel.PUBLIC
                    )
            except Exception as e:
                self._logger.warning(f"转换技能文件失败 {filepath}: {e}")

    def uninstall_skill(self, name: str) -> Dict[str, Any]:
        """
        卸载技能
        
        Args:
            name: 技能名称
            
        Returns:
            卸载结果
        """
        install_path = os.path.join(self._install_dir, name)
        
        if not os.path.exists(install_path):
            return {"success": False, "message": f"技能未安装: {name}"}

        try:
            shutil.rmtree(install_path)
            self._logger.info(f"卸载技能成功: {name}")
            return {"success": True, "message": "卸载成功"}
            
        except Exception as e:
            self._logger.error(f"卸载技能失败 {name}: {e}")
            return {"success": False, "message": str(e)}

    def update_skill(self, name: str) -> Dict[str, Any]:
        """
        更新技能
        
        Args:
            name: 技能名称
            
        Returns:
            更新结果
        """
        source = self._finder.get_source_info(name)
        if not source or not source.get("installed"):
            return {"success": False, "message": f"技能未安装: {name}"}

        install_path = os.path.join(self._install_dir, name)
        
        try:
            result = subprocess.run(
                ["git", "pull"],
                cwd=install_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                # 重新注册
                self._convert_and_register_skill(name)
                return {"success": True, "message": "更新成功"}
            else:
                return {"success": False, "message": f"更新失败: {result.stderr}"}
                
        except Exception as e:
            self._logger.error(f"更新技能失败 {name}: {e}")
            return {"success": False, "message": str(e)}

    def install_all_skills(self) -> Dict[str, Any]:
        """
        安装所有技能
        
        Returns:
            安装结果统计
        """
        sources = self._finder.get_all_sources()
        results = {
            "success": [],
            "failed": [],
            "skipped": []
        }

        for source in sources:
            if not source.enabled:
                results["skipped"].append(source.name)
                continue
            
            result = self.install_skill(source.name)
            if result["success"]:
                results["success"].append(source.name)
            else:
                results["failed"].append((source.name, result["message"]))

        self._logger.info(f"批量安装完成: 成功 {len(results['success'])}，失败 {len(results['failed'])}，跳过 {len(results['skipped'])}")
        
        return {
            "success": True,
            "installed_count": len(results["success"]),
            "failed_count": len(results["failed"]),
            "skipped_count": len(results["skipped"]),
            "installed": results["success"],
            "failed": results["failed"],
            "skipped": results["skipped"]
        }

    def install_by_category(self, category: str) -> Dict[str, Any]:
        """
        按类别安装技能
        
        Args:
            category: 类别名称
            
        Returns:
            安装结果统计
        """
        sources = self._finder.get_sources_by_category(category)
        results = {
            "success": [],
            "failed": []
        }

        for source in sources:
            result = self.install_skill(source.name)
            if result["success"]:
                results["success"].append(source.name)
            else:
                results["failed"].append((source.name, result["message"]))

        return {
            "success": True,
            "category": category,
            "installed_count": len(results["success"]),
            "failed_count": len(results["failed"]),
            "installed": results["success"],
            "failed": results["failed"]
        }

    def get_installed_skills(self) -> List[Dict[str, Any]]:
        """
        获取已安装的技能列表
        
        Returns:
            已安装技能列表
        """
        installed = []
        
        for name in os.listdir(self._install_dir):
            path = os.path.join(self._install_dir, name)
            if os.path.isdir(path):
                source_info = self._finder.get_source_info(name)
                installed.append({
                    "name": name,
                    "path": path,
                    **(source_info or {})
                })
        
        return installed

    def get_skill_status(self, name: str) -> Dict[str, Any]:
        """
        获取技能状态
        
        Args:
            name: 技能名称
            
        Returns:
            技能状态
        """
        source_info = self._finder.get_source_info(name)
        
        if not source_info:
            return {"name": name, "status": "unknown", "installed": False}

        status = "installed" if source_info["installed"] else "not_installed"
        
        return {
            "name": name,
            "status": status,
            "installed": source_info["installed"],
            "url": source_info.get("url"),
            "category": source_info.get("category"),
            "description": source_info.get("description"),
            "author": source_info.get("author"),
            "local_path": source_info.get("local_path")
        }

    def search_skills(self, query: str) -> List[Dict[str, Any]]:
        """
        搜索技能
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的技能列表
        """
        sources = self._finder.search_sources(query)
        results = []
        
        for source in sources:
            status = self.get_skill_status(source.name)
            results.append(status)
        
        return results

    def sync_skills(self):
        """
        同步所有已安装技能
        
        检查更新并重新注册
        """
        installed = self.get_installed_skills()
        
        for skill in installed:
            self._logger.info(f"同步技能: {skill['name']}")
            self._convert_and_register_skill(skill['name'])

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息
        """
        all_sources = self._finder.get_all_sources()
        installed = self.get_installed_skills()
        
        category_counts = {}
        for source in all_sources:
            category_counts[source.category] = category_counts.get(source.category, 0) + 1
        
        return {
            "total_sources": len(all_sources),
            "installed_count": len(installed),
            "categories": category_counts,
            "installed_names": [s["name"] for s in installed]
        }