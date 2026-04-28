"""
SkillVersionControl - 技能版本控制

参考 Multica 的版本控制设计，实现技能的版本管理。

功能：
1. 技能版本创建和管理
2. 版本比较和回滚
3. 版本分支管理
4. 版本发布和归档
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import json


class VersionStatus(Enum):
    """版本状态"""
    DRAFT = "draft"
    TESTING = "testing"
    RELEASED = "released"
    ARCHIVED = "archived"


class VersionChangeType(Enum):
    """变更类型"""
    FEATURE = "feature"      # 新功能
    BUGFIX = "bugfix"        # Bug修复
    IMPROVEMENT = "improvement"  # 改进
    REFACTOR = "refactor"    # 重构
    DOCUMENTATION = "documentation"  # 文档


@dataclass
class SkillVersion:
    """技能版本"""
    version_id: str
    skill_id: str
    version_number: str  # 语义版本号，如 1.0.0
    status: VersionStatus = VersionStatus.DRAFT
    change_type: VersionChangeType = VersionChangeType.FEATURE
    changelog: str = ""
    code: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    released_at: Optional[datetime] = None
    author: str = "system"


@dataclass
class VersionDiff:
    """版本差异"""
    skill_id: str
    from_version: str
    to_version: str
    added: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    modified: List[str] = field(default_factory=list)


class SkillVersionControl:
    """
    技能版本控制系统
    
    核心功能：
    1. 技能版本创建和管理
    2. 版本比较和回滚
    3. 版本分支管理
    4. 版本发布和归档
    """
    
    def __init__(self):
        self._logger = logger.bind(component="SkillVersionControl")
        self._versions: Dict[str, List[SkillVersion]] = {}  # skill_id -> [versions]
        self._branches: Dict[str, str] = {}  # branch_name -> latest_version_id
    
    def create_version(self, skill_id: str, change_type: VersionChangeType = VersionChangeType.FEATURE,
                      changelog: str = "", code: str = "", author: str = "system") -> SkillVersion:
        """
        创建新版本
        
        Args:
            skill_id: 技能 ID
            change_type: 变更类型
            changelog: 变更日志
            code: 技能代码
            author: 作者
            
        Returns:
            新建的版本
        """
        # 获取当前版本号
        current_version = self.get_latest_version(skill_id)
        new_version_number = self._increment_version(current_version.version_number if current_version else "0.0.0")
        
        version_id = f"version_{skill_id}_{new_version_number}"
        
        version = SkillVersion(
            version_id=version_id,
            skill_id=skill_id,
            version_number=new_version_number,
            change_type=change_type,
            changelog=changelog,
            code=code,
            author=author
        )
        
        if skill_id not in self._versions:
            self._versions[skill_id] = []
        
        self._versions[skill_id].append(version)
        self._logger.info(f"创建版本: {skill_id} v{new_version_number}")
        
        return version
    
    def _increment_version(self, current_version: str) -> str:
        """递增版本号"""
        parts = current_version.split(".")
        major, minor, patch = map(int, parts)
        
        # 默认递增 patch 版本
        return f"{major}.{minor}.{patch + 1}"
    
    def increment_major_version(self, skill_id: str) -> SkillVersion:
        """递增主版本号"""
        current_version = self.get_latest_version(skill_id)
        current_number = current_version.version_number if current_version else "0.0.0"
        
        parts = current_number.split(".")
        major, minor, patch = map(int, parts)
        new_version_number = f"{major + 1}.0.0"
        
        version_id = f"version_{skill_id}_{new_version_number}"
        version = SkillVersion(
            version_id=version_id,
            skill_id=skill_id,
            version_number=new_version_number,
            change_type=VersionChangeType.FEATURE,
            changelog=f"重大更新，主版本升级到 {major + 1}"
        )
        
        self._versions[skill_id].append(version)
        return version
    
    def increment_minor_version(self, skill_id: str) -> SkillVersion:
        """递增次版本号"""
        current_version = self.get_latest_version(skill_id)
        current_number = current_version.version_number if current_version else "0.0.0"
        
        parts = current_number.split(".")
        major, minor, patch = map(int, parts)
        new_version_number = f"{major}.{minor + 1}.0"
        
        version_id = f"version_{skill_id}_{new_version_number}"
        version = SkillVersion(
            version_id=version_id,
            skill_id=skill_id,
            version_number=new_version_number,
            change_type=VersionChangeType.FEATURE,
            changelog=f"新增功能，次版本升级到 {minor + 1}"
        )
        
        self._versions[skill_id].append(version)
        return version
    
    def get_version(self, skill_id: str, version_number: str) -> Optional[SkillVersion]:
        """获取指定版本"""
        versions = self._versions.get(skill_id, [])
        for version in versions:
            if version.version_number == version_number:
                return version
        return None
    
    def get_latest_version(self, skill_id: str) -> Optional[SkillVersion]:
        """获取最新版本"""
        versions = self._versions.get(skill_id, [])
        if not versions:
            return None
        
        # 按版本号排序
        versions.sort(key=lambda v: self._version_key(v.version_number), reverse=True)
        return versions[0]
    
    def _version_key(self, version_number: str) -> tuple:
        """版本号排序键"""
        parts = version_number.split(".")
        return tuple(map(int, parts))
    
    def get_all_versions(self, skill_id: str) -> List[SkillVersion]:
        """获取技能的所有版本"""
        versions = self._versions.get(skill_id, [])
        versions.sort(key=lambda v: self._version_key(v.version_number), reverse=True)
        return versions
    
    def compare_versions(self, skill_id: str, version1: str, version2: str) -> VersionDiff:
        """
        比较两个版本
        
        Args:
            skill_id: 技能 ID
            version1: 版本号1
            version2: 版本号2
            
        Returns:
            版本差异
        """
        v1 = self.get_version(skill_id, version1)
        v2 = self.get_version(skill_id, version2)
        
        if not v1 or not v2:
            return VersionDiff(skill_id=skill_id, from_version=version1, to_version=version2)
        
        # 简单的代码差异分析
        diff = VersionDiff(skill_id=skill_id, from_version=version1, to_version=version2)
        
        if v1.code != v2.code:
            diff.modified.append("技能代码")
        
        if v1.changelog != v2.changelog:
            diff.modified.append("变更日志")
        
        return diff
    
    def rollback_to_version(self, skill_id: str, version_number: str) -> bool:
        """
        回滚到指定版本
        
        Args:
            skill_id: 技能 ID
            version_number: 目标版本号
            
        Returns:
            是否回滚成功
        """
        target_version = self.get_version(skill_id, version_number)
        if not target_version:
            return False
        
        # 创建回滚版本
        current_version = self.get_latest_version(skill_id)
        rollback_version = SkillVersion(
            version_id=f"version_{skill_id}_rollback_to_{version_number}",
            skill_id=skill_id,
            version_number=self._increment_version(current_version.version_number if current_version else "0.0.0"),
            change_type=VersionChangeType.BUGFIX,
            changelog=f"回滚到版本 {version_number}",
            code=target_version.code
        )
        
        self._versions[skill_id].append(rollback_version)
        self._logger.info(f"回滚到版本: {skill_id} v{version_number}")
        
        return True
    
    def release_version(self, skill_id: str, version_number: str) -> bool:
        """
        发布版本
        
        Args:
            skill_id: 技能 ID
            version_number: 版本号
            
        Returns:
            是否发布成功
        """
        version = self.get_version(skill_id, version_number)
        if not version:
            return False
        
        version.status = VersionStatus.RELEASED
        version.released_at = datetime.now()
        self._logger.info(f"发布版本: {skill_id} v{version_number}")
        
        return True
    
    def archive_version(self, skill_id: str, version_number: str) -> bool:
        """
        归档版本
        
        Args:
            skill_id: 技能 ID
            version_number: 版本号
            
        Returns:
            是否归档成功
        """
        version = self.get_version(skill_id, version_number)
        if not version:
            return False
        
        version.status = VersionStatus.ARCHIVED
        self._logger.info(f"归档版本: {skill_id} v{version_number}")
        
        return True
    
    def create_branch(self, branch_name: str, skill_id: str, base_version: str = None):
        """
        创建分支
        
        Args:
            branch_name: 分支名称
            skill_id: 技能 ID
            base_version: 基础版本号（默认为最新版本）
        """
        if not base_version:
            latest = self.get_latest_version(skill_id)
            base_version = latest.version_number if latest else "0.0.0"
        
        self._branches[branch_name] = f"{skill_id}@{base_version}"
        self._logger.info(f"创建分支: {branch_name} -> {skill_id}@{base_version}")
    
    def get_branch_version(self, branch_name: str) -> Optional[SkillVersion]:
        """获取分支的当前版本"""
        branch_info = self._branches.get(branch_name)
        if not branch_info:
            return None
        
        skill_id, version_number = branch_info.split("@")
        return self.get_version(skill_id, version_number)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        version_counts = {}
        status_counts = {}
        
        for skill_id, versions in self._versions.items():
            version_counts[skill_id] = len(versions)
            
            for version in versions:
                status_counts[version.status.value] = status_counts.get(version.status.value, 0) + 1
        
        return {
            "total_skills": len(self._versions),
            "total_versions": sum(len(v) for v in self._versions.values()),
            "versions_per_skill": version_counts,
            "status_counts": status_counts,
            "total_branches": len(self._branches)
        }