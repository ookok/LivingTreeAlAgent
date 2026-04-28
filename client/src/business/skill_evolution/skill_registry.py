"""
SkillRegistry - 技能注册中心

统一管理技能的注册、版本管控、审计日志、权限管理。

遵循自我进化原则：
- 支持跨团队技能共享
- 自动记录审计日志
- 支持技能版本管理
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum


class SkillStatus(Enum):
    """技能状态"""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class PermissionLevel(Enum):
    """权限级别"""
    PUBLIC = "public"
    TEAM = "team"
    PRIVATE = "private"


@dataclass
class SkillVersion:
    """技能版本"""
    version_id: str
    version_number: str
    created_at: datetime
    created_by: str
    changes: str
    is_active: bool = True


@dataclass
class Skill:
    """技能"""
    skill_id: str
    name: str
    description: str
    category: str
    status: SkillStatus
    permission_level: PermissionLevel
    team_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    versions: List[SkillVersion] = field(default_factory=list)
    usage_count: int = 0


@dataclass
class AuditRecord:
    """审计记录"""
    record_id: str
    action: str
    skill_id: str
    user_id: str
    timestamp: datetime
    details: Dict[str, Any]


class SkillRegistry:
    """
    技能注册中心
    
    统一管理技能的注册、版本管控、审计日志、权限管理。
    """

    def __init__(self):
        self._logger = logger.bind(component="SkillRegistry")
        self._skills: Dict[str, Skill] = {}
        self._audit_logs: List[AuditRecord] = []
        self._teams: Dict[str, List[str]] = {}  # team_id -> [user_ids]

    def register_skill(
        self,
        skill_id: str,
        name: str,
        description: str,
        category: str,
        permission_level: PermissionLevel = PermissionLevel.PUBLIC,
        team_id: Optional[str] = None,
        user_id: str = "system"
    ) -> Skill:
        """
        注册技能
        
        Args:
            skill_id: 技能 ID
            name: 技能名称
            description: 技能描述
            category: 技能类别
            permission_level: 权限级别
            team_id: 团队 ID（可选）
            user_id: 用户 ID
            
        Returns:
            Skill
        """
        if skill_id in self._skills:
            raise ValueError(f"技能已存在: {skill_id}")

        skill = Skill(
            skill_id=skill_id,
            name=name,
            description=description,
            category=category,
            status=SkillStatus.DRAFT,
            permission_level=permission_level,
            team_id=team_id
        )

        # 创建初始版本
        initial_version = SkillVersion(
            version_id=f"{skill_id}_v1",
            version_number="1.0",
            created_at=datetime.now(),
            created_by=user_id,
            changes="Initial version"
        )
        skill.versions.append(initial_version)

        self._skills[skill_id] = skill
        
        # 记录审计日志
        self._add_audit_log("register", skill_id, user_id, {"name": name})
        
        self._logger.info(f"已注册技能: {name}")
        return skill

    def update_skill(
        self,
        skill_id: str,
        user_id: str,
        **kwargs
    ) -> Skill:
        """
        更新技能
        
        Args:
            skill_id: 技能 ID
            user_id: 用户 ID
            kwargs: 更新的字段
            
        Returns:
            Skill
        """
        if skill_id not in self._skills:
            raise ValueError(f"技能不存在: {skill_id}")

        skill = self._skills[skill_id]
        
        # 更新字段
        for key, value in kwargs.items():
            if hasattr(skill, key):
                setattr(skill, key, value)
        
        skill.updated_at = datetime.now()
        
        # 记录审计日志
        self._add_audit_log("update", skill_id, user_id, kwargs)
        
        self._logger.info(f"已更新技能: {skill_id}")
        return skill

    def publish_skill(self, skill_id: str, user_id: str) -> Skill:
        """
        发布技能
        
        Args:
            skill_id: 技能 ID
            user_id: 用户 ID
            
        Returns:
            Skill
        """
        if skill_id not in self._skills:
            raise ValueError(f"技能不存在: {skill_id}")

        skill = self._skills[skill_id]
        skill.status = SkillStatus.ACTIVE
        skill.updated_at = datetime.now()
        
        # 记录审计日志
        self._add_audit_log("publish", skill_id, user_id, {})
        
        self._logger.info(f"已发布技能: {skill.name}")
        return skill

    def deprecate_skill(self, skill_id: str, user_id: str) -> Skill:
        """
        废弃技能
        
        Args:
            skill_id: 技能 ID
            user_id: 用户 ID
            
        Returns:
            Skill
        """
        if skill_id not in self._skills:
            raise ValueError(f"技能不存在: {skill_id}")

        skill = self._skills[skill_id]
        skill.status = SkillStatus.DEPRECATED
        skill.updated_at = datetime.now()
        
        # 记录审计日志
        self._add_audit_log("deprecate", skill_id, user_id, {})
        
        self._logger.info(f"已废弃技能: {skill.name}")
        return skill

    def add_version(self, skill_id: str, user_id: str, changes: str) -> SkillVersion:
        """
        添加技能版本
        
        Args:
            skill_id: 技能 ID
            user_id: 用户 ID
            changes: 变更说明
            
        Returns:
            SkillVersion
        """
        if skill_id not in self._skills:
            raise ValueError(f"技能不存在: {skill_id}")

        skill = self._skills[skill_id]
        
        # 计算新版本号
        last_version = skill.versions[-1]
        major, minor = map(int, last_version.version_number.split("."))
        new_version_number = f"{major}.{minor + 1}"
        
        new_version = SkillVersion(
            version_id=f"{skill_id}_v{major}.{minor + 1}",
            version_number=new_version_number,
            created_at=datetime.now(),
            created_by=user_id,
            changes=changes
        )
        
        # 禁用旧版本
        last_version.is_active = False
        
        skill.versions.append(new_version)
        skill.updated_at = datetime.now()
        
        # 记录审计日志
        self._add_audit_log("version", skill_id, user_id, {"version": new_version_number, "changes": changes})
        
        self._logger.info(f"已添加技能版本: {skill_id} v{new_version_number}")
        return new_version

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills.get(skill_id)

    def list_skills(
        self,
        user_id: Optional[str] = None,
        team_id: Optional[str] = None,
        status: Optional[SkillStatus] = None,
        category: Optional[str] = None
    ) -> List[Skill]:
        """
        列出技能
        
        Args:
            user_id: 用户 ID（用于权限检查）
            team_id: 团队 ID
            status: 技能状态
            category: 技能类别
            
        Returns:
            技能列表
        """
        skills = list(self._skills.values())
        
        # 过滤
        if status:
            skills = [s for s in skills if s.status == status]
        
        if category:
            skills = [s for s in skills if s.category == category]
        
        # 权限过滤
        if user_id:
            accessible = []
            for skill in skills:
                if skill.permission_level == PermissionLevel.PUBLIC:
                    accessible.append(skill)
                elif skill.permission_level == PermissionLevel.TEAM:
                    # 检查用户是否在团队中
                    if team_id and team_id == skill.team_id:
                        accessible.append(skill)
                elif skill.permission_level == PermissionLevel.PRIVATE:
                    # 私有技能需要特殊权限检查
                    pass
            skills = accessible
        
        return skills

    def record_usage(self, skill_id: str):
        """记录技能使用"""
        if skill_id in self._skills:
            self._skills[skill_id].usage_count += 1

    def _add_audit_log(self, action: str, skill_id: str, user_id: str, details: Dict[str, Any]):
        """添加审计日志"""
        record = AuditRecord(
            record_id=f"audit_{len(self._audit_logs)}",
            action=action,
            skill_id=skill_id,
            user_id=user_id,
            timestamp=datetime.now(),
            details=details
        )
        self._audit_logs.append(record)

    def get_audit_logs(
        self,
        skill_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[AuditRecord]:
        """
        获取审计日志
        
        Args:
            skill_id: 技能 ID
            user_id: 用户 ID
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            审计记录列表
        """
        logs = self._audit_logs.copy()
        
        if skill_id:
            logs = [l for l in logs if l.skill_id == skill_id]
        
        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        
        if start_time:
            logs = [l for l in logs if l.timestamp >= start_time]
        
        if end_time:
            logs = [l for l in logs if l.timestamp <= end_time]
        
        return logs

    def create_team(self, team_id: str, name: str):
        """创建团队"""
        if team_id in self._teams:
            raise ValueError(f"团队已存在: {team_id}")
        self._teams[team_id] = []
        self._logger.info(f"已创建团队: {name}")

    def add_user_to_team(self, team_id: str, user_id: str):
        """添加用户到团队"""
        if team_id not in self._teams:
            raise ValueError(f"团队不存在: {team_id}")
        if user_id not in self._teams[team_id]:
            self._teams[team_id].append(user_id)
            self._logger.info(f"已添加用户 {user_id} 到团队 {team_id}")

    def get_stats(self) -> Dict[str, Any]:
        """获取注册中心统计信息"""
        active_count = sum(1 for s in self._skills.values() if s.status == SkillStatus.ACTIVE)
        draft_count = sum(1 for s in self._skills.values() if s.status == SkillStatus.DRAFT)
        total_versions = sum(len(s.versions) for s in self._skills.values())
        
        return {
            "total_skills": len(self._skills),
            "active_skills": active_count,
            "draft_skills": draft_count,
            "total_versions": total_versions,
            "total_teams": len(self._teams),
            "total_audit_records": len(self._audit_logs),
            "total_usage": sum(s.usage_count for s in self._skills.values())
        }