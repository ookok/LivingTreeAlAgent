"""
SkillFinder - 技能发现器

发现和检索外部技能源，支持 GitHub、PyPI 等多种来源。
"""

from typing import Dict, Any, Optional, List
from loguru import logger
import os
import subprocess
import json

from .distillation_config import SkillSource, DistillationConfig, DEFAULT_SKILL_SOURCES


class SkillFinder:
    """技能发现器"""

    def __init__(self):
        self._logger = logger.bind(component="SkillFinder")
        self._config = DistillationConfig(sources=DEFAULT_SKILL_SOURCES)

    def get_all_sources(self) -> List[SkillSource]:
        """获取所有技能源"""
        return self._config.sources

    def get_sources_by_category(self, category: str) -> List[SkillSource]:
        """按类别获取技能源"""
        return self._config.get_sources_by_category(category)

    def search_sources(self, query: str) -> List[SkillSource]:
        """
        搜索技能源
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的技能源列表
        """
        results = []
        query_lower = query.lower()
        
        for source in self._config.sources:
            score = 0
            
            if query_lower in source.name.lower():
                score += 3
            if query_lower in source.description.lower():
                score += 2
            if query_lower in source.category.lower():
                score += 1
            for tag in source.tags:
                if query_lower in tag.lower():
                    score += 1
            
            if score > 0:
                results.append((source, score))
        
        # 按相关性排序
        results.sort(key=lambda x: x[1], reverse=True)
        return [r[0] for r in results]

    def get_source_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取技能源详细信息
        
        Args:
            name: 技能源名称
            
        Returns:
            技能源信息字典
        """
        source = self._config.get_source(name)
        if not source:
            return None

        info = source.to_dict()
        
        # 检查本地是否已安装
        install_path = self._get_install_path(source.name)
        info["installed"] = os.path.exists(install_path)
        info["local_path"] = install_path
        
        return info

    def check_github_repo(self, url: str) -> Dict[str, Any]:
        """
        检查 GitHub 仓库信息
        
        Args:
            url: GitHub 仓库 URL
            
        Returns:
            仓库信息
        """
        try:
            # 尝试使用 git 命令获取信息
            result = subprocess.run(
                ["git", "ls-remote", "--get-url", url],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return {
                    "exists": True,
                    "url": result.stdout.strip(),
                    "error": None
                }
            else:
                return {
                    "exists": False,
                    "url": url,
                    "error": result.stderr.strip()
                }
                
        except Exception as e:
            self._logger.warning(f"检查 GitHub 仓库失败 {url}: {e}")
            return {
                "exists": False,
                "url": url,
                "error": str(e)
            }

    def discover_new_skills(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        发现新技能
        
        Args:
            keywords: 搜索关键词列表
            
        Returns:
            发现的技能列表
        """
        discovered = []
        
        for keyword in keywords:
            results = self.search_sources(keyword)
            for source in results:
                if source.name not in [d["name"] for d in discovered]:
                    discovered.append(source.to_dict())
        
        return discovered

    def validate_source(self, source: SkillSource) -> bool:
        """
        验证技能源是否有效
        
        Args:
            source: 技能源
            
        Returns:
            是否有效
        """
        if source.type == "github":
            info = self.check_github_repo(source.url)
            return info["exists"]
        
        # 本地路径检查
        if source.type == "local":
            return os.path.exists(source.url)
        
        return True

    def get_categories(self) -> List[str]:
        """获取所有类别"""
        categories = set()
        for source in self._config.sources:
            categories.add(source.category)
        return sorted(list(categories))

    def _get_install_path(self, name: str) -> str:
        """获取安装路径"""
        install_dir = os.path.expanduser(self._config.default_install_dir)
        return os.path.join(install_dir, name)

    def update_config(self, config: DistillationConfig):
        """更新配置"""
        self._config = config

    def add_custom_source(self, name: str, url: str, category: str = "other", 
                          description: str = "", author: str = ""):
        """
        添加自定义技能源
        
        Args:
            name: 技能名称
            url: 技能 URL
            category: 类别
            description: 描述
            author: 作者
        """
        if self._config.get_source(name):
            self._logger.warning(f"技能源已存在: {name}")
            return False

        source = SkillSource(
            name=name,
            url=url,
            type=self._detect_source_type(url),
            category=category,
            description=description,
            author=author
        )
        self._config.add_source(source)
        self._logger.info(f"添加技能源: {name}")
        return True

    def _detect_source_type(self, url: str) -> str:
        """检测源类型"""
        if url.startswith("https://github.com/"):
            return "github"
        elif url.startswith("https://pypi.org/"):
            return "pypi"
        elif os.path.exists(url):
            return "local"
        else:
            return "api"