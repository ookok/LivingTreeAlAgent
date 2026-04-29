"""
LocalResources 文件定位器

自动从 localresources 目录查找匹配的测试资源文件：
- 根据文件类型匹配
- 根据内容关键词匹配
- 根据文件名模式匹配
- 优先级排序
"""

import os
import re
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from pathlib import Path
from enum import Enum
import fnmatch


class FileCategory(Enum):
    """文件类别"""
    PYTHON = "python"
    JSON = "json"
    MARKDOWN = "markdown"
    TEXT = "text"
    CONFIG = "config"
    OTHER = "other"


@dataclass
class ResourceFile:
    """资源文件"""
    path: str  # 相对于 localresources 的路径
    full_path: str  # 完整路径
    category: FileCategory
    size: int
    name: str
    extension: str
    keywords: List[str]  # 从文件名提取的关键词

    @property
    def relevance_score(self) -> float:
        """计算相关性分数"""
        return len(self.keywords) * 0.1


@dataclass
class SearchCriteria:
    """搜索条件"""
    keywords: List[str] = None  # 关键词列表
    extensions: List[str] = None  # 文件扩展名
    categories: List[FileCategory] = None  # 文件类别
    min_size: int = 0  # 最小大小
    max_size: int = 10 * 1024 * 1024  # 最大 10MB
    pattern: str = ""  # 文件名模式（glob）


class ResourceLocator:
    """
    LocalResources 文件定位器

    Usage:
        locator = ResourceLocator(project_root="d:/mhzyapp/LivingTreeAlAgent")
        locator.scan()  # 扫描资源

        # 根据关键词查找
        files = locator.find_by_keywords(["message", "chat"])
        # 找 Python 文件
        files = locator.find_by_extension(".py")
        # 根据内容查找
        files = locator.find_by_content("def send_message")
    """

    # 扩展名到类别的映射
    EXTENSION_CATEGORY_MAP = {
        ".py": FileCategory.PYTHON,
        ".json": FileCategory.JSON,
        ".md": FileCategory.MARKDOWN,
        ".txt": FileCategory.TEXT,
        ".yaml": FileCategory.CONFIG,
        ".yml": FileCategory.CONFIG,
        ".toml": FileCategory.CONFIG,
        ".ini": FileCategory.CONFIG,
        ".cfg": FileCategory.CONFIG,
    }

    def __init__(
        self,
        project_root: str = None,
        localresources_path: str = None,
        cache_enabled: bool = True
    ):
        self._project_root = project_root or os.getcwd()
        self._localresources_path = localresources_path or os.path.join(
            self._project_root, "localresources"
        )
        self._cache_enabled = cache_enabled
        self._scan_cache: Dict[str, List[ResourceFile]] = {}
        self._index_built = False

        # 关键词到扩展名的推荐映射
        self._keyword_extension_hints = {
            "config": [".json", ".yaml", ".toml", ".ini"],
            "test": [".py"],
            "model": [".json", ".py"],
            "api": [".py", ".json"],
            "ui": [".py"],
            "panel": [".py"],
            "widget": [".py"],
            "component": [".py"],
            "business": [".py"],
            "data": [".json", ".txt"],
            "message": [".py", ".json"],
            "chat": [".py", ".json"],
            "tool": [".py", ".json"],
            "agent": [".py"],
            "workflow": [".py", ".json"],
        }

    def scan(self, force: bool = False) -> List[ResourceFile]:
        """
        扫描 localresources 目录

        Args:
            force: 是否强制重新扫描

        Returns:
            资源文件列表
        """
        cache_key = self._localresources_path

        if self._cache_enabled and not force and cache_key in self._scan_cache:
            return self._scan_cache[cache_key]

        files: List[ResourceFile] = []

        if not os.path.exists(self._localresources_path):
            return files

        for root, dirs, filenames in os.walk(self._localresources_path):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, self._localresources_path)

                try:
                    size = os.path.getsize(full_path)
                    ext = os.path.splitext(filename)[1].lower()
                    category = self.EXTENSION_CATEGORY_MAP.get(ext, FileCategory.OTHER)

                    # 提取文件名中的关键词
                    keywords = self._extract_keywords(filename)

                    files.append(ResourceFile(
                        path=rel_path,
                        full_path=full_path,
                        category=category,
                        size=size,
                        name=filename,
                        extension=ext,
                        keywords=keywords
                    ))
                except Exception:
                    continue

        if self._cache_enabled:
            self._scan_cache[cache_key] = files

        self._index_built = True
        return files

    def _extract_keywords(self, filename: str) -> List[str]:
        """从文件名提取关键词"""
        # 移除扩展名
        name = os.path.splitext(filename)[0]
        # 转换为小写
        name = name.lower()
        # 分割驼峰和下划线
        words = re.split(r'[_\-]+', name)
        # 过滤掉太短的词
        words = [w for w in words if len(w) >= 2]
        return words

    def find(
        self,
        criteria: SearchCriteria = None,
        limit: int = 10
    ) -> List[ResourceFile]:
        """
        根据条件查找文件

        Args:
            criteria: 搜索条件
            limit: 返回数量限制

        Returns:
            匹配的文件列表（按相关性排序）
        """
        files = self.scan()

        if criteria is None:
            criteria = SearchCriteria()

        results = []

        for f in files:
            # 扩展名过滤
            if criteria.extensions:
                if f.extension not in criteria.extensions:
                    continue

            # 类别过滤
            if criteria.categories:
                if f.category not in criteria.categories:
                    continue

            # 大小过滤
            if f.size < criteria.min_size or f.size > criteria.max_size:
                continue

            # 模式匹配
            if criteria.pattern:
                if not fnmatch.fnmatch(f.name, criteria.pattern):
                    continue

            # 关键词匹配
            score = 0
            if criteria.keywords:
                for kw in criteria.keywords:
                    kw_lower = kw.lower()
                    # 检查文件名
                    if kw_lower in f.name.lower():
                        score += 2
                    # 检查关键词列表
                    if kw_lower in f.keywords:
                        score += 1
                    # 检查路径
                    if kw_lower in f.path.lower():
                        score += 0.5
            else:
                score = f.relevance_score

            if score > 0 or not criteria.keywords:
                results.append((f, score))

        # 按相关性排序
        results.sort(key=lambda x: x[1], reverse=True)

        return [f for f, _ in results[:limit]]

    def find_by_keywords(
        self,
        keywords: List[str],
        extensions: List[str] = None,
        limit: int = 10
    ) -> List[ResourceFile]:
        """根据关键词查找文件"""
        return self.find(
            SearchCriteria(
                keywords=keywords,
                extensions=extensions
            ),
            limit=limit
        )

    def find_by_extension(
        self,
        extension: str,
        limit: int = 20
    ) -> List[ResourceFile]:
        """根据扩展名查找文件"""
        exts = [extension] if not isinstance(extension, list) else extension
        return self.find(
            SearchCriteria(extensions=exts),
            limit=limit
        )

    def find_python_files(
        self,
        keywords: List[str] = None,
        limit: int = 10
    ) -> List[ResourceFile]:
        """查找 Python 文件"""
        return self.find_by_keywords(
            keywords or [],
            extensions=[".py"],
            limit=limit
        )

    def find_json_files(
        self,
        keywords: List[str] = None,
        limit: int = 10
    ) -> List[ResourceFile]:
        """查找 JSON 文件"""
        return self.find_by_keywords(
            keywords or [],
            extensions=[".json"],
            limit=limit
        )

    def find_test_data(
        self,
        related_file: str = None,
        limit: int = 5
    ) -> List[ResourceFile]:
        """
        查找测试数据文件

        策略：
        1. 如果提供了相关文件名，提取关键词
        2. 优先查找同名的测试数据
        3. 查找 .json, .txt 等数据文件
        """
        keywords = []

        if related_file:
            # 从文件名提取关键词
            name = os.path.splitext(os.path.basename(related_file))[0]
            keywords = self._extract_keywords(name)

        # 优先查找数据文件
        candidates = []

        # 1. 查找同名文件（不同扩展名）
        if related_file:
            base = os.path.splitext(related_file)[0]
            candidates.extend(self.find(
                SearchCriteria(pattern=f"*{os.path.basename(base)}*"),
                limit=5
            ))

        # 2. 查找 .json 数据文件
        candidates.extend(self.find_json_files(keywords, limit=5))

        # 3. 查找 .txt 文件
        candidates.extend(self.find_by_extension([".txt"], limit=5))

        # 去重并排序
        seen = set()
        unique = []
        for f in candidates:
            if f.path not in seen:
                seen.add(f.path)
                unique.append(f)

        return unique[:limit]

    def suggest_extensions(self, keywords: List[str]) -> List[str]:
        """根据关键词建议文件扩展名"""
        suggestions = set()

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in self._keyword_extension_hints:
                suggestions.update(self._keyword_extension_hints[kw_lower])

        return list(suggestions)

    def get_file_content(self, resource: ResourceFile) -> Optional[str]:
        """获取文件内容"""
        try:
            with open(resource.full_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return None

    def get_relative_path(self, resource: ResourceFile) -> str:
        """获取相对于项目根目录的路径"""
        return os.path.join("localresources", resource.path)


# ─────────────────────────────────────────────────────────────────────────────
# 便捷函数
# ─────────────────────────────────────────────────────────────────────────────

# 全局实例
_global_locator: Optional[ResourceLocator] = None


def get_resource_locator(project_root: str = None) -> ResourceLocator:
    """获取全局资源定位器"""
    global _global_locator
    if _global_locator is None:
        _global_locator = ResourceLocator(project_root)
    return _global_locator


def find_test_resource(
    keywords: List[str],
    project_root: str = None,
    extensions: List[str] = None
) -> Optional[str]:
    """
    便捷函数：查找测试资源文件

    Args:
        keywords: 搜索关键词
        project_root: 项目根目录
        extensions: 文件扩展名过滤

    Returns:
        文件完整路径，如果没有找到返回 None
    """
    locator = get_resource_locator(project_root)
    files = locator.find_by_keywords(keywords, extensions, limit=1)
    return files[0].full_path if files else None


def find_test_data_file(
    related_to: str,
    project_root: str = None
) -> Optional[str]:
    """
    便捷函数：查找关联的测试数据文件

    Args:
        related_to: 关联的文件路径
        project_root: 项目根目录

    Returns:
        测试数据文件路径
    """
    locator = get_resource_locator(project_root)
    files = locator.find_test_data(related_to, limit=1)
    return files[0].full_path if files else None
