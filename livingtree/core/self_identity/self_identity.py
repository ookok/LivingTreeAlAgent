"""
自我身份系统 - 核心实现

实现元认知能力："我知道我知道什么，我知道我不知道什么"
"""
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class KPIDefinition:
    """KPI定义"""
    name: str
    description: str
    target: float  # 目标值
    current: float = 0.0
    unit: str = ""
    severity: str = "medium"  # high, medium, low
    category: str = "performance"
    
    @property
    def achieved(self) -> bool:
        """是否达到目标"""
        return self.current >= self.target
    
    @property
    def progress(self) -> float:
        """完成进度百分比"""
        return min((self.current / self.target) * 100, 100)


@dataclass
class SkillProfile:
    """技能档案"""
    skill_id: str
    name: str
    level: int = 1  # 1-5级
    experience: int = 0
    last_used: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class IdentityAuditResult:
    """身份审计结果"""
    success: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    kpi_status: Dict[str, bool] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)


class SelfIdentity:
    """
    自我身份系统
    
    核心能力：
    1. 维护职业身份定义
    2. 监控KPI指标
    3. 元认知自我审查
    4. Idle循环自动优化
    """
    
    DEFAULT_IDENTITY = {
        "role": "高级环保咨询工程师和Python开发者",
        "specialties": ["环评报告", "可行性研究", "财务分析", "Python开发"],
        "values": ["专业", "严谨", "创新", "持续学习"],
        "kpis": {
            "code_coverage": {"target": 0.85, "unit": "%", "severity": "high"},
            "report_format_correctness": {"target": 1.0, "unit": "%", "severity": "high"},
            "code_quality_score": {"target": 0.8, "unit": "", "severity": "medium"},
            "test_pass_rate": {"target": 0.95, "unit": "%", "severity": "high"},
            "response_time": {"target": 10, "unit": "秒", "severity": "medium"},
        },
        "skills": [],
        "knowledge": {
            "domains": ["环境科学", "金融分析", "软件开发"],
            "tools": ["Python", "PyQt", "LangChain", "Pandas"],
            "certifications": [],
        },
        "goals": [
            "成为行业领先的AI辅助咨询专家",
            "持续提升代码质量和自动化能力",
            "扩展专业知识领域",
        ]
    }
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".livingtree" / "self_identity.json"
        self.identity = self.DEFAULT_IDENTITY.copy()
        self.skills: Dict[str, SkillProfile] = {}
        self._load_identity()
        
        # Idle循环状态
        self.is_idle_running = False
        self.idle_interval = 300  # 5分钟检查一次
    
    def _load_identity(self):
        """加载身份定义"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.identity.update(data)
                    logger.info("✅ 已加载自我身份定义")
            except Exception as e:
                logger.warning(f"⚠️ 加载身份定义失败，使用默认值: {e}")
        
        # 初始化技能
        for skill_data in self.identity.get("skills", []):
            self.skills[skill_data["skill_id"]] = SkillProfile(**skill_data)
    
    def _save_identity(self):
        """保存身份定义"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            # 更新技能列表
            self.identity["skills"] = [skill.__dict__ for skill in self.skills.values()]
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.identity, f, ensure_ascii=False, indent=2)
            logger.debug("✅ 已保存自我身份定义")
        except Exception as e:
            logger.error(f"❌ 保存身份定义失败: {e}")
    
    def update_role(self, role: str):
        """更新职业角色"""
        self.identity["role"] = role
        self._save_identity()
        logger.info(f"👤 更新职业角色: {role}")
    
    def add_skill(self, skill_id: str, name: str, level: int = 1):
        """添加技能"""
        if skill_id not in self.skills:
            self.skills[skill_id] = SkillProfile(
                skill_id=skill_id,
                name=name,
                level=level,
                last_used=datetime.now().isoformat()
            )
            self._save_identity()
            logger.info(f"➕ 添加技能: {name} (Lv.{level})")
    
    def update_skill_level(self, skill_id: str, level: int):
        """更新技能等级"""
        if skill_id in self.skills:
            self.skills[skill_id].level = level
            self.skills[skill_id].experience += 10
            self.skills[skill_id].last_used = datetime.now().isoformat()
            self._save_identity()
            logger.info(f"📈 技能升级: {self.skills[skill_id].name} → Lv.{level}")
    
    def get_kpi_definitions(self) -> List[KPIDefinition]:
        """获取所有KPI定义"""
        kpis = []
        for name, config in self.identity["kpis"].items():
            kpis.append(KPIDefinition(
                name=name,
                description=name.replace("_", " ").title(),
                target=config["target"],
                unit=config.get("unit", ""),
                severity=config.get("severity", "medium"),
            ))
        return kpis
    
    def update_kpi(self, name: str, value: float):
        """更新KPI值"""
        if name in self.identity["kpis"]:
            self.identity["kpis"][name]["current"] = value
            self._save_identity()
    
    def get_kpi(self, name: str) -> Optional[KPIDefinition]:
        """获取单个KPI"""
        if name in self.identity["kpis"]:
            config = self.identity["kpis"][name]
            return KPIDefinition(
                name=name,
                description=name.replace("_", " ").title(),
                target=config["target"],
                current=config.get("current", 0.0),
                unit=config.get("unit", ""),
                severity=config.get("severity", "medium"),
            )
        return None
    
    def self_audit(self) -> IdentityAuditResult:
        """
        自我审查
        
        检查KPI达标情况，并生成改进建议。
        """
        issues = []
        warnings = []
        kpi_status = {}
        suggestions = []
        
        # 检查每个KPI
        for kpi in self.get_kpi_definitions():
            kpi_status[kpi.name] = kpi.achieved
            
            if not kpi.achieved:
                if kpi.severity == "high":
                    issues.append(f"🚨 KPI未达标: {kpi.description} (当前: {kpi.current}{kpi.unit}, 目标: {kpi.target}{kpi.unit})")
                else:
                    warnings.append(f"⚠️ KPI接近阈值: {kpi.description} (进度: {kpi.progress:.1f}%)")
        
        # 检查技能覆盖
        skill_gaps = self._identify_skill_gaps()
        if skill_gaps:
            suggestions.extend([f"建议学习: {skill}" for skill in skill_gaps])
        
        # 基于身份的自我审查
        role = self.identity["role"]
        if "工程师" in role:
            # 工程师身份特定检查
            code_kpi = self.get_kpi("code_coverage")
            if code_kpi and not code_kpi.achieved:
                suggestions.append("作为工程师，代码覆盖率需要提升")
        
        if "咨询" in role:
            # 咨询师身份特定检查
            report_kpi = self.get_kpi("report_format_correctness")
            if report_kpi and not report_kpi.achieved:
                suggestions.append("作为咨询师，报告格式需要优化")
        
        return IdentityAuditResult(
            success=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            kpi_status=kpi_status,
            suggestions=suggestions
        )
    
    def _identify_skill_gaps(self) -> List[str]:
        """识别技能缺口"""
        gaps = []
        
        # 根据专业领域识别缺口
        domains = self.identity["knowledge"]["domains"]
        
        if "环境科学" in domains and "环评计算" not in self.skills:
            gaps.append("环评计算")
        
        if "金融分析" in domains and "财务建模" not in self.skills:
            gaps.append("财务建模")
        
        return gaps
    
    def schedule_improvement(self, audit_result: IdentityAuditResult):
        """
        根据审计结果安排改进任务
        
        在Idle时间执行改进。
        """
        # 收集需要改进的KPI
        pending_improvements = []
        
        for issue in audit_result.issues:
            if "代码覆盖率" in issue:
                pending_improvements.append(("code_coverage", "提升代码覆盖率"))
            elif "报告格式" in issue:
                pending_improvements.append(("report_format", "优化报告格式"))
        
        if pending_improvements:
            logger.info(f"📋 安排改进任务: {pending_improvements}")
            
            # 在Idle时间执行
            self._schedule_idle_task(lambda: self._execute_improvements(pending_improvements))
    
    def _execute_improvements(self, improvements: List[Tuple[str, str]]):
        """执行改进任务"""
        for improvement_type, description in improvements:
            logger.info(f"🔧 执行改进: {description}")
            
            if improvement_type == "code_coverage":
                self._improve_code_coverage()
            elif improvement_type == "report_format":
                self._improve_report_format()
    
    def _improve_code_coverage(self):
        """提升代码覆盖率（示例实现）"""
        logger.info("📈 分析现有测试覆盖率...")
        # 实际实现中：运行测试、分析覆盖率、生成缺失的测试用例
        self.update_kpi("code_coverage", min(0.9, self.get_kpi("code_coverage").current + 0.05))
    
    def _improve_report_format(self):
        """优化报告格式（示例实现）"""
        logger.info("🎨 优化报告模板...")
        # 实际实现中：检查报告格式、更新模板、添加样式
        self.update_kpi("report_format_correctness", 1.0)
    
    def _schedule_idle_task(self, task: callable):
        """安排Idle任务"""
        if self.is_idle_running:
            # 在Idle循环中执行
            logger.debug("任务已加入Idle队列")
    
    def start_idle_loop(self):
        """启动Idle循环"""
        self.is_idle_running = True
        import threading
        thread = threading.Thread(target=self._idle_loop, daemon=True)
        thread.start()
        logger.info("🚀 Idle循环启动")
    
    def _idle_loop(self):
        """Idle循环"""
        while self.is_idle_running:
            time.sleep(self.idle_interval)
            self._idle_check()
    
    def _idle_check(self):
        """Idle检查"""
        audit_result = self.self_audit()
        
        if not audit_result.success:
            logger.info("🔍 Idle检查发现问题，安排改进")
            self.schedule_improvement(audit_result)
    
    def stop_idle_loop(self):
        """停止Idle循环"""
        self.is_idle_running = False
        logger.info("🛑 Idle循环停止")
    
    def get_identity_summary(self) -> Dict[str, Any]:
        """获取身份摘要"""
        return {
            "role": self.identity["role"],
            "specialties": self.identity["specialties"],
            "kpi_summary": {k: v["target"] for k, v in self.identity["kpis"].items()},
            "skill_count": len(self.skills),
            "domains": self.identity["knowledge"]["domains"],
        }


# 单例模式
_self_identity = None


def get_self_identity() -> SelfIdentity:
    """获取自我身份单例"""
    global _self_identity
    if _self_identity is None:
        _self_identity = SelfIdentity()
    return _self_identity