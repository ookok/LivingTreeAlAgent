"""
Safety Fence - 安全围栏
保护IDE自我进化过程中的代码安全、数据安全和系统安全
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from ..proposal.structured_proposal import StructuredProposal, RiskLevel

logger = logging.getLogger(__name__)


class SafetyCategory(Enum):
    """安全类别"""
    CODE_SAFETY = "code_safety"           # 代码安全
    DATA_SAFETY = "data_safety"           # 数据安全
    SYSTEM_SAFETY = "system_safety"       # 系统安全
    PERMISSION_SAFETY = "permission_safety"  # 权限安全


@dataclass
class SafetyViolation:
    """安全违规"""
    category: SafetyCategory
    rule_name: str
    description: str
    severity: RiskLevel
    affected_paths: List[str]
    suggestion: str


class SafetyRule:
    """安全规则"""
    
    # 禁止修改的路径模式
    FORBIDDEN_PATTERNS = [
        "**/node_modules/**",
        "**/.git/**",
        "**/__pycache__/**",
        "**/*.pyc",
        "**/.venv/**",
        "**/venv/**",
        "**/env/**",
        "**/.env",
        "**/config/secrets.yaml",
        "**/credentials.json",
        "**/.aws/**",
        "**/id_rsa*",
        "**/.ssh/**",
    ]
    
    # 高风险操作
    HIGH_RISK_OPERATIONS = [
        "rm -rf",
        "del /s /q",
        "shutil.rmtree",
        "DROP TABLE",
        "DELETE FROM",
        "TRUNCATE",
        "format",
        "mkfs",
    ]
    
    # 允许的最大变更范围（单次操作）
    MAX_CHANGE_SIZE_MB = 10
    
    @classmethod
    def is_forbidden_path(cls, path: str) -> bool:
        """检查路径是否禁止修改"""
        from fnmatch import fnmatch
        
        path = os.path.abspath(path)
        for pattern in cls.FORBIDDEN_PATTERNS:
            if fnmatch(path, pattern) or fnmatch(path.replace("\\", "/"), pattern):
                return True
        return False
    
    @classmethod
    def contains_high_risk_operation(cls, content: str) -> bool:
        """检查内容是否包含高风险操作"""
        content_lower = content.lower()
        for op in cls.HIGH_RISK_OPERATIONS:
            if op.lower() in content_lower:
                return True
        return False


class SafetyFence:
    """安全围栏"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.logger = logging.getLogger(__name__)
        self.violations: List[SafetyViolation] = []
        self.enabled = True
    
    def validate_proposal(self, proposal: StructuredProposal) -> bool:
        """
        验证提案安全性
        
        Args:
            proposal: 待验证的提案
            
        Returns:
            True 表示安全，False 表示存在风险
        """
        if not self.enabled:
            return True
        
        self.violations.clear()
        
        # 检查每个执行步骤
        for step in proposal.steps:
            violations = self._validate_step(step)
            self.violations.extend(violations)
        
        # 高风险提案需要额外确认
        if proposal.estimated_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            # 检查是否有足够的风险缓解措施
            if not self._has_mitigation(proposal):
                self.violations.append(SafetyViolation(
                    category=SafetyCategory.CODE_SAFETY,
                    rule_name="high_risk_no_mitigation",
                    description="高风险提案缺少风险缓解措施",
                    severity=RiskLevel.HIGH,
                    affected_paths=[],
                    suggestion="请确保有备份和回滚方案"
                ))
        
        # 阻止高严重度违规
        critical_violations = [v for v in self.violations 
                               if v.severity == RiskLevel.CRITICAL]
        
        if critical_violations:
            self.logger.error(f"提案 {proposal.proposal_id} 被安全围栏阻止: "
                            f"{len(critical_violations)} 个严重违规")
            return False
        
        return True
    
    def _validate_step(self, step) -> List[SafetyViolation]:
        """验证单个步骤"""
        violations = []
        
        # 检查目标路径
        if step.target:
            if SafetyRule.is_forbidden_path(step.target):
                violations.append(SafetyViolation(
                    category=SafetyCategory.CODE_SAFETY,
                    rule_name="forbidden_path",
                    description=f"禁止修改路径: {step.target}",
                    severity=RiskLevel.CRITICAL,
                    affected_paths=[step.target],
                    suggestion="请选择允许的代码目录"
                ))
        
        # 检查变更内容
        if step.changes:
            changes_str = str(step.changes)
            if SafetyRule.contains_high_risk_operation(changes_str):
                violations.append(SafetyViolation(
                    category=SafetyCategory.SYSTEM_SAFETY,
                    rule_name="high_risk_operation",
                    description=f"包含高风险操作: {changes_str[:100]}",
                    severity=RiskLevel.CRITICAL,
                    affected_paths=[step.target] if step.target else [],
                    suggestion="请使用安全的替代方案"
                ))
        
        # 检查变更大小
        if step.changes:
            estimated_size = self._estimate_change_size(step.changes)
            if estimated_size > SafetyRule.MAX_CHANGE_SIZE_MB:
                violations.append(SafetyViolation(
                    category=SafetyCategory.DATA_SAFETY,
                    rule_name="change_too_large",
                    description=f"变更大小 ({estimated_size}MB) 超过限制 ({SafetyRule.MAX_CHANGE_SIZE_MB}MB)",
                    severity=RiskLevel.HIGH,
                    affected_paths=[step.target] if step.target else [],
                    suggestion="请分批进行变更"
                ))
        
        return violations
    
    def _has_mitigation(self, proposal: StructuredProposal) -> bool:
        """检查是否有风险缓解措施"""
        # 检查是否所有步骤都是可逆的
        all_reversible = all(step.reversible for step in proposal.steps)
        
        # 检查是否有测试步骤
        has_test = any(step.action_type == "test" for step in proposal.steps)
        
        # 检查是否需要确认
        requires_confirmation = any(step.requires_confirmation 
                                   for step in proposal.steps)
        
        return all_reversible and has_test and requires_confirmation
    
    def _estimate_change_size(self, changes: Dict[str, Any]) -> float:
        """估算变更大小（MB）"""
        changes_str = str(changes)
        return len(changes_str.encode('utf-8')) / (1024 * 1024)
    
    def get_violations_report(self) -> str:
        """获取违规报告"""
        if not self.violations:
            return "✅ 未检测到安全违规"
        
        report_lines = ["⚠️ 安全违规报告:", ""]
        
        # 按类别分组
        by_category = {}
        for v in self.violations:
            if v.category not in by_category:
                by_category[v.category] = []
            by_category[v.category].append(v)
        
        for category, violations in by_category.items():
            report_lines.append(f"### {category.value}")
            for v in violations:
                severity_icon = "🔴" if v.severity == RiskLevel.CRITICAL else \
                               "🟠" if v.severity == RiskLevel.HIGH else \
                               "🟡" if v.severity == RiskLevel.MEDIUM else "🟢"
                report_lines.append(f"{severity_icon} [{v.rule_name}] {v.description}")
                if v.affected_paths:
                    report_lines.append(f"   影响路径: {', '.join(v.affected_paths)}")
                report_lines.append(f"   💡 建议: {v.suggestion}")
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    def check_permission(self, action: str, path: Optional[str] = None) -> bool:
        """
        检查权限
        
        Args:
            action: 操作类型
            path: 目标路径
            
        Returns:
            True 表示有权限，False 表示无权限
        """
        # 检查路径权限
        if path:
            abs_path = os.path.abspath(path)
            project_abs = os.path.abspath(self.project_root)
            
            # 不允许修改项目外部的文件
            if not abs_path.startswith(project_abs):
                self.logger.warning(f"尝试修改项目外部文件: {path}")
                return False
        
        return True
    
    def create_backup(self, path: str) -> Optional[str]:
        """
        创建备份
        
        Args:
            path: 需要备份的路径
            
        Returns:
            备份路径，失败返回 None
        """
        try:
            import shutil
            from datetime import datetime
            
            source = Path(path)
            if not source.exists():
                return None
            
            # 创建备份目录
            backup_dir = self.project_root / ".evolution_backups"
            backup_dir.mkdir(exist_ok=True)
            
            # 生成备份文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source.name}_{timestamp}.bak"
            backup_path = backup_dir / backup_name
            
            # 复制文件
            if source.is_file():
                shutil.copy2(source, backup_path)
            else:
                shutil.copytree(source, backup_path)
            
            self.logger.info(f"已创建备份: {backup_path}")
            return str(backup_path)
        
        except Exception as e:
            self.logger.error(f"创建备份失败: {e}")
            return None
    
    def enable(self) -> None:
        """启用安全围栏"""
        self.enabled = True
        self.logger.info("安全围栏已启用")
    
    def disable(self) -> None:
        """禁用安全围栏（谨慎使用）"""
        self.enabled = False
        self.logger.warning("安全围栏已禁用")
