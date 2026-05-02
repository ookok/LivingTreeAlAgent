"""
选择性同步 - Selective Sync

控制哪些文件夹/文件需要同步：
- 同步排除规则
- 同步包含规则
- 文件类型过滤
- 大小限制
"""

import os
import fnmatch
import re
from typing import List, Set, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path

from .models import FileInfo, FolderConfig


@dataclass
class SyncFilter:
    """同步过滤器配置"""
    # 排除模式 (glob)
    exclude_patterns: List[str] = field(default_factory=list)

    # 包含模式 (glob) - 优先级更高
    include_patterns: List[str] = field(default_factory=list)

    # 文件类型过滤器
    allowed_extensions: Set[str] = field(default_factory=set)  # 空 = 全部允许
    blocked_extensions: Set[str] = field(default_factory=set)

    # 大小限制
    max_file_size: int = 0  # 0 = 无限制
    min_file_size: int = 0

    # 特殊规则
    include_hidden: bool = False  # 包含隐藏文件
    include_symlinks: bool = False  # 包含符号链接


class SelectiveSync:
    """
    选择性同步

    决定哪些文件应该被同步：
    1. 路径匹配
    2. 文件类型过滤
    3. 大小限制
    4. 包含/排除规则
    """

    def __init__(self, config: FolderConfig):
        self.folder_config = config
        self.filter = SyncFilter()

        # 从文件夹配置初始化
        self.filter.exclude_patterns = config.ignore_patterns.copy()

        # 预编译正则
        self._exclude_regex: List[re.Pattern] = []
        self._include_regex: List[re.Pattern] = []

    def set_exclude_patterns(self, patterns: List[str]):
        """设置排除模式"""
        self.filter.exclude_patterns = patterns.copy()
        self._compile_patterns()

    def set_include_patterns(self, patterns: List[str]):
        """设置包含模式"""
        self.filter.include_patterns = patterns.copy()
        self._compile_patterns()

    def add_exclude_pattern(self, pattern: str):
        """添加排除模式"""
        if pattern not in self.filter.exclude_patterns:
            self.filter.exclude_patterns.append(pattern)
            self._compile_patterns()

    def add_include_pattern(self, pattern: str):
        """添加包含模式"""
        if pattern not in self.filter.include_patterns:
            self.filter.include_patterns.append(pattern)
            self._compile_patterns()

    def _compile_patterns(self):
        """编译 glob 模式为正则"""
        self._exclude_regex = []
        self._include_regex = []

        for pattern in self.filter.exclude_patterns:
            # 转换为正则
            regex_pattern = fnmatch.translate(pattern)
            self._exclude_regex.append(re.compile(regex_pattern))

        for pattern in self.filter.include_patterns:
            regex_pattern = fnmatch.translate(pattern)
            self._include_regex.append(re.compile(regex_pattern))

    def should_sync(self, file_path: str, file_info: Optional[FileInfo] = None) -> bool:
        """
        判断文件是否应该同步

        Args:
            file_path: 文件路径（相对于同步文件夹）
            file_info: 文件信息（可选）

        Returns:
            True = 需要同步
        """
        # 检查包含规则（优先级最高）
        if self._include_regex:
            for regex in self._include_regex:
                if regex.search(file_path):
                    return True
            # 不匹配任何包含规则
            return False

        # 检查排除规则
        for regex in self._exclude_regex:
            if regex.search(file_path):
                return False

        # 检查隐藏文件
        if not self.filter.include_hidden:
            name = os.path.basename(file_path)
            if name.startswith('.') or '/.' in file_path or '\\.' in file_path:
                return False

        # 检查符号链接
        if not self.filter.include_symlinks:
            if file_info and file_info.is_symlink:
                return False

        # 检查扩展名
        if self.filter.allowed_extensions:
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in self.filter.allowed_extensions:
                return False

        if self.filter.blocked_extensions:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in self.filter.blocked_extensions:
                return False

        # 检查文件大小
        if file_info:
            if self.filter.max_file_size > 0:
                if file_info.size > self.filter.max_file_size:
                    return False

            if self.filter.min_file_size > 0:
                if file_info.size < self.filter.min_file_size:
                    return False

        return True

    def filter_file_list(self, files: List[FileInfo],
                        base_path: str = "") -> List[FileInfo]:
        """
        过滤文件列表

        Args:
            files: 文件信息列表
            base_path: 基础路径

        Returns:
            过滤后的文件列表
        """
        result = []

        for file_info in files:
            # 计算相对路径
            if base_path:
                file_path = os.path.join(base_path, file_info.name)
            else:
                file_path = file_info.name

            if self.should_sync(file_path, file_info):
                result.append(file_info)

        return result

    def get_excluded_count(self, total: int, excluded: int) -> dict:
        """获取排除统计"""
        return {
            "total": total,
            "excluded": excluded,
            "included": total - excluded,
            "exclusion_rate": f"{(excluded/total*100):.1f}%" if total > 0 else "0%",
        }


class SyncRuleManager:
    """
    同步规则管理器

    管理多个同步规则集：
    - 全局规则
    - 文件夹特定规则
    - 临时规则
    """

    GLOBAL_RULES_KEY = "__global__"

    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 规则集
        self._rules: dict = {}

        # 加载
        self._load_rules()

    def add_rule(self, name: str, patterns: List[str],
                rule_type: str = "exclude"):
        """添加规则"""
        if name not in self._rules:
            self._rules[name] = {"exclude": [], "include": []}

        if rule_type == "exclude":
            self._rules[name]["exclude"].extend(patterns)
        else:
            self._rules[name]["include"].extend(patterns)

        self._save_rules()

    def remove_rule(self, name: str, pattern: str):
        """移除规则"""
        if name not in self._rules:
            return

        for rule_type in ["exclude", "include"]:
            if pattern in self._rules[name][rule_type]:
                self._rules[name][rule_type].remove(pattern)

        self._save_rules()

    def get_rules(self, name: str = GLOBAL_RULES_KEY) -> dict:
        """获取规则集"""
        return self._rules.get(name, {"exclude": [], "include": []})

    def apply_rules(self, path: str, rules_name: str = GLOBAL_RULES_KEY) -> bool:
        """
        应用规则判断是否同步

        Returns:
            True = 同步, False = 排除
        """
        rules = self._rules.get(rules_name, {"exclude": [], "include": []})

        # 先检查排除
        for pattern in rules.get("exclude", []):
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern):
                # 检查是否有包含规则覆盖
                for inc_pattern in rules.get("include", []):
                    if fnmatch.fnmatch(path, inc_pattern):
                        return True
                return False

        return True

    def _load_rules(self):
        """加载规则"""
        import json

        rules_file = self.storage_path / "sync_rules.json"
        if rules_file.exists():
            try:
                with open(rules_file, "r") as f:
                    self._rules = json.load(f)
            except Exception:
                pass

    def _save_rules(self):
        """保存规则"""
        import json

        rules_file = self.storage_path / "sync_rules.json"
        with open(rules_file, "w") as f:
            json.dump(self._rules, f)
