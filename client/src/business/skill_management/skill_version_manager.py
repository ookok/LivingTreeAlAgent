"""
SkillVersionManager - 技能版本管理器

实现技能版本管理功能：
1. 版本号管理（SemVer）
2. 版本历史查看
3. 版本差异对比
4. 版本回滚

借鉴 Skill Compose 的技能版本管理理念

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import time
import json


class VersionStatus(Enum):
    """版本状态"""
    ACTIVE = "active"       # 当前活跃版本
    ARCHIVED = "archived"   # 已归档
    DEPRECATED = "deprecated" # 已废弃


@dataclass
class ToolVersion:
    """
    工具版本
    
    记录工具的一个版本信息。
    """
    version: str             # 版本号（SemVer格式）
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    changelog: str = ""      # 更新日志
    status: VersionStatus = VersionStatus.ACTIVE
    content_hash: str = ""   # 内容哈希（用于差异对比）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "changelog": self.changelog,
            "status": self.status.value,
            "content_hash": self.content_hash
        }


@dataclass
class VersionDiff:
    """
    版本差异
    
    记录两个版本之间的差异。
    """
    from_version: str
    to_version: str
    added: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    modified: List[str] = field(default_factory=list)


class SkillVersionManager:
    """
    技能版本管理器
    
    功能：
    1. 为每个工具管理多个版本
    2. 支持版本历史查看
    3. 支持版本差异对比
    4. 支持版本回滚
    5. 遵循SemVer版本规范
    """
    
    def __init__(self):
        self._logger = logger.bind(component="SkillVersionManager")
        
        # 版本存储：tool_name -> List[ToolVersion]
        self._versions: Dict[str, List[ToolVersion]] = {}
        
        self._logger.info("✅ SkillVersionManager 初始化完成")
    
    def add_version(self, tool_name: str, version: str, changelog: str = "", content_hash: str = ""):
        """
        添加新版本
        
        Args:
            tool_name: 工具名称
            version: 版本号（SemVer格式）
            changelog: 更新日志
            content_hash: 内容哈希
        """
        # 验证版本号格式
        if not self._validate_semver(version):
            self._logger.warning(f"❌ 无效的版本号格式: {version}")
            return False
        
        # 检查版本是否已存在
        if tool_name not in self._versions:
            self._versions[tool_name] = []
        
        existing_versions = [v.version for v in self._versions[tool_name]]
        if version in existing_versions:
            self._logger.warning(f"❌ 版本已存在: {tool_name} v{version}")
            return False
        
        # 创建新版本
        tool_version = ToolVersion(
            version=version,
            changelog=changelog,
            content_hash=content_hash,
            status=VersionStatus.ACTIVE
        )
        
        self._versions[tool_name].append(tool_version)
        
        # 按版本号排序
        self._versions[tool_name].sort(key=lambda v: self._parse_semver(v.version), reverse=True)
        
        self._logger.info(f"➕ 添加版本: {tool_name} v{version}")
        return True
    
    def _validate_semver(self, version: str) -> bool:
        """
        验证SemVer格式
        
        Args:
            version: 版本号
            
        Returns:
            是否有效
        """
        import re
        pattern = r'^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$'
        return bool(re.match(pattern, version))
    
    def _parse_semver(self, version: str) -> tuple:
        """
        解析SemVer版本号为元组（用于排序）
        
        Args:
            version: 版本号
            
        Returns:
            (major, minor, patch, prerelease)
        """
        import re
        pattern = r'^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+))?'
        match = re.match(pattern, version)
        if match:
            return (
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                match.group(4) or ""
            )
        return (0, 0, 0, "")
    
    def get_versions(self, tool_name: str) -> List[ToolVersion]:
        """
        获取工具的所有版本
        
        Args:
            tool_name: 工具名称
            
        Returns:
            版本列表（按版本号降序排列）
        """
        return self._versions.get(tool_name, [])
    
    def get_latest_version(self, tool_name: str) -> Optional[ToolVersion]:
        """
        获取最新版本
        
        Args:
            tool_name: 工具名称
            
        Returns:
            最新版本（如果存在）
        """
        versions = self.get_versions(tool_name)
        return versions[0] if versions else None
    
    def get_version(self, tool_name: str, version: str) -> Optional[ToolVersion]:
        """
        获取指定版本
        
        Args:
            tool_name: 工具名称
            version: 版本号
            
        Returns:
            指定版本（如果存在）
        """
        versions = self.get_versions(tool_name)
        for v in versions:
            if v.version == version:
                return v
        return None
    
    def compare_versions(self, tool_name: str, version1: str, version2: str) -> Optional[VersionDiff]:
        """
        比较两个版本的差异（简化实现）
        
        Args:
            tool_name: 工具名称
            version1: 版本1
            version2: 版本2
            
        Returns:
            版本差异（如果存在）
        """
        v1 = self.get_version(tool_name, version1)
        v2 = self.get_version(tool_name, version2)
        
        if not v1 or not v2:
            return None
        
        # 简单的差异对比（基于内容哈希）
        diff = VersionDiff(
            from_version=version1,
            to_version=version2
        )
        
        # 如果内容哈希不同，标记为修改
        if v1.content_hash != v2.content_hash:
            diff.modified.append("tool_content")
        
        # 检查更新日志差异
        if v1.changelog != v2.changelog:
            diff.modified.append("changelog")
        
        return diff
    
    def rollback(self, tool_name: str, target_version: str) -> bool:
        """
        回滚到指定版本
        
        Args:
            tool_name: 工具名称
            target_version: 目标版本
            
        Returns:
            是否成功
        """
        version = self.get_version(tool_name, target_version)
        if not version:
            self._logger.warning(f"❌ 版本不存在: {tool_name} v{target_version}")
            return False
        
        # 将目标版本设置为活跃状态
        for v in self._versions[tool_name]:
            if v.version == target_version:
                v.status = VersionStatus.ACTIVE
            else:
                v.status = VersionStatus.ARCHIVED
        
        self._logger.info(f"🔄 回滚版本: {tool_name} -> v{target_version}")
        return True
    
    def deprecate_version(self, tool_name: str, version: str):
        """
        废弃指定版本
        
        Args:
            tool_name: 工具名称
            version: 版本号
        """
        version = self.get_version(tool_name, version)
        if version:
            version.status = VersionStatus.DEPRECATED
            self._logger.info(f"🚫 废弃版本: {tool_name} v{version.version}")
    
    def get_version_history(self, tool_name: str) -> List[Dict[str, Any]]:
        """
        获取版本历史（按时间顺序）
        
        Args:
            tool_name: 工具名称
            
        Returns:
            版本历史列表
        """
        versions = self.get_versions(tool_name)
        return [v.to_dict() for v in versions]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_tools = len(self._versions)
        total_versions = sum(len(vs) for vs in self._versions.values())
        
        return {
            "total_tools": total_tools,
            "total_versions": total_versions,
            "average_versions_per_tool": total_versions / max(total_tools, 1)
        }


# 创建全局实例
skill_version_manager = SkillVersionManager()


def get_skill_version_manager() -> SkillVersionManager:
    """获取技能版本管理器实例"""
    return skill_version_manager


# 测试函数
async def test_skill_version_manager():
    """测试技能版本管理器"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 SkillVersionManager")
    print("=" * 60)
    
    manager = SkillVersionManager()
    
    # 1. 添加版本
    print("\n[1] 添加版本...")
    manager.add_version("weather_tool", "1.0.0", "初始版本")
    manager.add_version("weather_tool", "1.1.0", "添加实时天气查询")
    manager.add_version("weather_tool", "2.0.0", "重写核心逻辑")
    print(f"    ✓ 添加了3个版本")
    
    # 2. 获取版本列表
    print("\n[2] 获取版本列表...")
    versions = manager.get_versions("weather_tool")
    print(f"    ✓ 版本数量: {len(versions)}")
    for v in versions:
        print(f"      - v{v.version} ({v.status.value})")
    
    # 3. 获取最新版本
    print("\n[3] 获取最新版本...")
    latest = manager.get_latest_version("weather_tool")
    print(f"    ✓ 最新版本: v{latest.version}")
    
    # 4. 比较版本差异
    print("\n[4] 比较版本差异...")
    diff = manager.compare_versions("weather_tool", "1.0.0", "2.0.0")
    print(f"    ✓ 差异: {diff.modified}")
    
    # 5. 版本回滚
    print("\n[5] 版本回滚...")
    success = manager.rollback("weather_tool", "1.1.0")
    print(f"    ✓ 回滚成功: {success}")
    
    # 6. 废弃版本
    print("\n[6] 废弃版本...")
    manager.deprecate_version("weather_tool", "1.0.0")
    v1 = manager.get_version("weather_tool", "1.0.0")
    print(f"    ✓ 版本1.0.0状态: {v1.status.value}")
    
    # 7. 获取版本历史
    print("\n[7] 获取版本历史...")
    history = manager.get_version_history("weather_tool")
    print(f"    ✓ 历史记录数: {len(history)}")
    
    # 8. 统计信息
    print("\n[8] 统计信息...")
    stats = manager.get_stats()
    print(f"    ✓ 工具数: {stats['total_tools']}")
    print(f"    ✓ 版本数: {stats['total_versions']}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_skill_version_manager())