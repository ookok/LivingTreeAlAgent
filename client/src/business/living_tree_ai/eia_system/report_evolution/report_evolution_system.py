"""
报告进化系统 - 智能报告"进化"系统
让报告能像软件一样"迭代升级"

核心能力：
1. 版本控制 + 语义差异
2. 自动生成修订说明
3. 合规性继承检查
"""

import asyncio
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ============================================================================
# 数据模型
# ============================================================================

class ChangeType(Enum):
    """变更类型"""
    MAJOR = "major"      # 重大修订（如排放标准更新）
    MINOR = "minor"      # 一般变更
    FORMAT = "format"    # 格式调整
    CORRECTION = "correction"  # 勘误


class RegulationStatus(Enum):
    """法规状态"""
    EFFECTIVE = "effective"    # 有效
    OBSOLETE = "obsolete"      # 已废止
    UPDATING = "updating"      # 即将更新
    PARTIALLY_EFFECTIVE = "partially_effective"  # 部分有效


@dataclass
class RegulationUpdate:
    """法规更新"""
    regulation_id: str
    name: str
    old_version: str
    new_version: str
    effective_date: datetime
    status: RegulationStatus
    affected_reports: list = field(default_factory=list)
    impact_level: str = "unknown"  # "high", "medium", "low"


@dataclass
class SemanticChange:
    """语义变更"""
    change_id: str
    change_type: ChangeType
    section: str
    field_name: str
    old_value: Any
    new_value: Any
    change_reason: str
    semantic_impact: str  # "重大修订", "技术调整", "格式变更"
    affected_content: list = field(default_factory=list)  # 影响的条文


@dataclass
class RevisionNote:
    """修订说明"""
    revision_id: str
    report_id: str
    from_version: str
    to_version: str
    revision_date: datetime
    changes: list = field(default_factory=list)  # SemanticChange列表
    auto_generated: bool = True
    content: str = ""  # 自动生成的修订说明文本
    reviewed: bool = False
    reviewed_by: str = ""


@dataclass
class ReportVersion:
    """报告版本"""
    version_id: str
    report_id: str
    version_number: str
    content: dict  # 完整内容快照
    content_hash: str
    created_at: datetime
    created_by: str
    changes_from_previous: list = field(default_factory=list)  # 变更列表
    regulation_updates: list = field(default_factory=list)  # 引用的法规更新
    status: str = "active"


@dataclass
class ComplianceInheritance:
    """合规性继承"""
    report_id: str
    version: str
    inherited_compliances: list = field(default_factory=list)  # 继承的合规要求
    new_compliances: list = field(default_factory=list)  # 新增的合规要求
    dropped_compliances: list = field(default_factory=list)  # 放弃的合规要求
    needs_update: bool = False
    update_reason: str = ""


# ============================================================================
# 语义差异分析器
# ============================================================================

class SemanticDiffAnalyzer:
    """语义差异分析器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._semantic_keywords = self._init_semantic_keywords()

    def _init_semantic_keywords(self) -> dict:
        """初始化语义关键词"""
        return {
            "emission_standard": {
                "keywords": ["排放标准", "GB", "限值", "标准限值"],
                "impact": "重大修订",
                "check": self._check_standard_change
            },
            "source_intensity": {
                "keywords": ["源强", "排放量", "产生量"],
                "impact": "技术调整",
                "check": self._check_source_change
            },
            "prediction_model": {
                "keywords": ["预测模型", "AERMOD", "模式", "参数"],
                "impact": "技术调整",
                "check": self._check_model_change
            },
            "scope": {
                "keywords": ["评价范围", "评价等级", "专题"],
                "impact": "重大修订",
                "check": self._check_scope_change
            }
        }

    async def analyze_diff(
        self,
        old_content: dict,
        new_content: dict
    ) -> list[SemanticChange]:
        """分析语义差异"""
        changes = []

        # 比较所有字段
        all_keys = set(list(old_content.keys()) + list(new_content.keys()))

        for key in all_keys:
            old_val = old_content.get(key)
            new_val = new_content.get(key)

            if old_val != new_val:
                change_type = self._classify_change_type(key, old_val, new_val)
                semantic_impact = self._get_semantic_impact(key)

                change = SemanticChange(
                    change_id=f"change_{uuid.uuid4().hex[:12]}",
                    change_type=change_type,
                    section=self._infer_section(key),
                    field_name=key,
                    old_value=old_val,
                    new_value=new_val,
                    change_reason=self._infer_reason(key, old_val, new_val),
                    semantic_impact=semantic_impact,
                    affected_content=await self._find_affected_content(key, new_content)
                )
                changes.append(change)

        return changes

    def _classify_change_type(self, key: str, old_val: Any, new_val: Any) -> ChangeType:
        """分类变更类型"""
        # 重大变更检测
        major_keywords = ["emission_standard", "standard", "regulation"]
        if any(k in key.lower() for k in major_keywords):
            return ChangeType.MAJOR

        # 格式变更检测
        if isinstance(old_val, str) and isinstance(new_val, str):
            if len(old_val) > 50 and len(new_val) > 50:
                return ChangeType.MINOR
            return ChangeType.FORMAT

        return ChangeType.MINOR

    def _get_semantic_impact(self, key: str) -> str:
        """获取语义影响"""
        for field_type, info in self._semantic_keywords.items():
            if any(kw in key for kw in info["keywords"]):
                return info["impact"]
        return "一般变更"

    def _infer_section(self, key: str) -> str:
        """推断章节"""
        section_map = {
            "source": "工程分析",
            "air": "大气环境影响",
            "water": "水环境影响",
            "noise": "声环境影响",
            "eco": "生态环境影响",
            "risk": "环境风险",
            "standard": "执行标准",
            "measure": "环保措施"
        }
        for sec, keywords in section_map.items():
            if sec in key.lower():
                return keywords
        return "其他"

    def _infer_reason(self, key: str, old_val: Any, new_val: Any) -> str:
        """推断变更原因"""
        if "standard" in key.lower():
            return f"标准更新：{old_val} → {new_val}"
        elif "regulation" in key.lower():
            return f"法规变化：{old_val} → {new_val}"
        elif isinstance(new_val, str) and len(new_val) > len(str(old_val)):
            return "内容补充完善"
        elif isinstance(new_val, str) and len(new_val) < len(str(old_val)):
            return "内容精简优化"
        return "技术调整"

    async def _find_affected_content(self, key: str, new_content: dict) -> list:
        """查找受影响的内容"""
        affected = []
        key_lower = key.lower()

        for field, value in new_content.items():
            if field == key:
                continue
            # 简单检查：是否与变更字段相关
            if any(related in field.lower() for related in key_lower.split("_")):
                affected.append({"field": field, "value": str(value)[:50]})

        return affected[:3]  # 最多返回3个

    def _check_standard_change(self, old_val: str, new_val: str) -> bool:
        """检查标准变更"""
        return old_val != new_val

    def _check_source_change(self, old_val: Any, new_val: Any) -> bool:
        """检查源强变更"""
        try:
            old_num = float(old_val) if old_val else 0
            new_num = float(new_val) if new_val else 0
            return abs(old_num - new_num) / max(old_num, 1) > 0.05  # 5%变化
        except:
            return old_val != new_val

    def _check_model_change(self, old_val: str, new_val: str) -> bool:
        """检查模型变更"""
        return old_val != new_val

    def _check_scope_change(self, old_val: Any, new_val: Any) -> bool:
        """检查范围变更"""
        return old_val != new_val


# ============================================================================
# 修订说明生成器
# ============================================================================

class RevisionNoteGenerator:
    """修订说明生成器"""

    def __init__(self, config: dict = None):
        self.config = config or {}

    def generate_revision_note(
        self,
        report_id: str,
        from_version: str,
        to_version: str,
        changes: list[SemanticChange]
    ) -> RevisionNote:
        """生成修订说明"""
        revision_id = f"rev_{uuid.uuid4().hex[:12]}"

        # 按类型分组
        major_changes = [c for c in changes if c.change_type == ChangeType.MAJOR]
        minor_changes = [c for c in changes if c.change_type == ChangeType.MINOR]
        format_changes = [c for c in changes if c.change_type == ChangeType.FORMAT]

        # 生成文本
        content_parts = []

        content_parts.append(f"## {report_id} 修订说明")
        content_parts.append(f"\n**修订版本**: {from_version} → {to_version}")
        content_parts.append(f"**修订日期**: {datetime.now().strftime('%Y-%m-%d')}")
        content_parts.append(f"\n---")

        if major_changes:
            content_parts.append("\n### 一、重大修订")
            for i, change in enumerate(major_changes, 1):
                content_parts.append(f"\n**{i}. [{change.section}] {change.field_name}**")
                content_parts.append(f"   - 变更前: {change.old_value}")
                content_parts.append(f"   - 变更后: {change.new_value}")
                content_parts.append(f"   - 原因: {change.change_reason}")
                if change.affected_content:
                    affected = [a["field"] for a in change.affected_content[:2]]
                    content_parts.append(f"   - 影响: {', '.join(affected)}")

        if minor_changes:
            content_parts.append("\n### 二、一般变更")
            for change in minor_changes[:5]:  # 最多5条
                content_parts.append(f"\n- [{change.section}] {change.field_name}: {change.old_value} → {change.new_value}")

        if format_changes:
            content_parts.append(f"\n### 三、格式调整")
            content_parts.append(f"共 {len(format_changes)} 处格式调整，包括编号、表述等。")

        # 添加合规性说明
        if major_changes:
            content_parts.append("\n### 四、合规性说明")
            content_parts.append("本次修订涉及重大变更，请确认是否符合现行法规要求。")

        content = "\n".join(content_parts)

        return RevisionNote(
            revision_id=revision_id,
            report_id=report_id,
            from_version=from_version,
            to_version=to_version,
            revision_date=datetime.now(),
            changes=changes,
            auto_generated=True,
            content=content
        )

    def generate_draft_chapter(
        self,
        revision_note: RevisionNote
    ) -> str:
        """生成修订章节草案"""
        sections = []

        sections.append("## 修订说明")

        for change in revision_note.changes:
            if change.change_type == ChangeType.MAJOR:
                sections.append(f"\n### {change.section}")
                sections.append(f"**{change.field_name}**")
                sections.append(f"本次修订将{change.field_name}由「{change.old_value}」调整为「{change.new_value}」。")
                sections.append(f"修订原因：{change.change_reason}。")

        return "\n".join(sections)


# ============================================================================
# 合规性继承检查器
# ============================================================================

class ComplianceInheritanceChecker:
    """合规性继承检查器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._regulation_db = self._load_regulation_db()

    def _load_regulation_db(self) -> dict:
        """加载法规数据库"""
        return {
            "GB16297": {
                "name": "大气污染物综合排放标准",
                "versions": ["1996", "202X"],
                "status": "updating"
            },
            "GB3838": {
                "name": "地表水环境质量标准",
                "versions": ["2002"],
                "status": "effective"
            },
            "HJ2.2": {
                "name": "环境影响评价技术导则 大气环境",
                "versions": ["2018"],
                "status": "effective"
            }
        }

    async def check_compliance_inheritance(
        self,
        old_content: dict,
        new_content: dict,
        regulation_updates: list[RegulationUpdate] = None
    ) -> ComplianceInheritance:
        """检查合规性继承"""
        regulation_updates = regulation_updates or []

        inherited = []
        new_compliances = []
        dropped = []

        # 检查引用的法规
        old_regulations = old_content.get("referenced_regulations", [])
        new_regulations = new_content.get("referenced_regulations", [])

        # 继承的合规要求
        for reg in old_regulations:
            if reg in new_regulations:
                inherited.append(reg)
            else:
                dropped.append(reg)

        # 新增的合规要求
        for reg in new_regulations:
            if reg not in old_regulations:
                new_compliances.append(reg)

        # 检查是否有法规更新需要应用
        needs_update = False
        update_reason = ""

        for update in regulation_updates:
            if update.regulation_id in new_regulations and update.status == RegulationStatus.UPDATING:
                needs_update = True
                update_reason += f"{update.name} 已更新至 {update.new_version}；"

        return ComplianceInheritance(
            report_id=new_content.get("report_id", ""),
            version=new_content.get("version", ""),
            inherited_compliances=inherited,
            new_compliances=new_compliances,
            dropped_compliances=dropped,
            needs_update=needs_update,
            update_reason=update_reason
        )

    def scan_for_updates(
        self,
        referenced_regulations: list[str]
    ) -> list[RegulationUpdate]:
        """扫描需要更新的法规"""
        updates = []

        for reg_id in referenced_regulations:
            if reg_id in self._regulation_db:
                reg = self._regulation_db[reg_id]
                if reg["status"] == "updating":
                    updates.append(RegulationUpdate(
                        regulation_id=reg_id,
                        name=reg["name"],
                        old_version=reg["versions"][-2] if len(reg["versions"]) > 1 else reg["versions"][0],
                        new_version=reg["versions"][-1],
                        effective_date=datetime.now(),
                        status=RegulationStatus.UPDATING,
                        impact_level="high"
                    ))

        return updates


# ============================================================================
# 报告进化引擎（主入口）
# ============================================================================

class ReportEvolutionEngine:
    """报告进化引擎"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.diff_analyzer = SemanticDiffAnalyzer(config)
        self.note_generator = RevisionNoteGenerator(config)
        self.compliance_checker = ComplianceInheritanceChecker(config)
        self._versions: dict = {}  # report_id -> list of versions
        self._current_content: dict = {}

    async def create_version(
        self,
        report_id: str,
        version_number: str,
        content: dict,
        created_by: str = "system"
    ) -> ReportVersion:
        """创建新版本"""
        version_id = f"ver_{uuid.uuid4().hex[:12]}"

        # 计算内容哈希
        content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]

        # 与上一版本比较
        changes = []
        if report_id in self._current_content:
            changes = await self.diff_analyzer.analyze_diff(
                self._current_content[report_id],
                content
            )

        version = ReportVersion(
            version_id=version_id,
            report_id=report_id,
            version_number=version_number,
            content=content,
            content_hash=content_hash,
            created_at=datetime.now(),
            created_by=created_by,
            changes_from_previous=changes
        )

        if report_id not in self._versions:
            self._versions[report_id] = []
        self._versions[report_id].append(version)
        self._current_content[report_id] = content

        return version

    async def generate_revision_note(
        self,
        report_id: str,
        from_version: str = None,
        to_version: str = None
    ) -> RevisionNote:
        """生成修订说明"""
        versions = self._versions.get(report_id, [])
        if not versions:
            raise ValueError(f"No versions found for report {report_id}")

        if len(versions) < 2:
            return None

        # 取最后两个版本
        old_ver = versions[-2]
        new_ver = versions[-1]

        from_v = from_version or old_ver.version_number
        to_v = to_version or new_ver.version_number

        return self.note_generator.generate_revision_note(
            report_id, from_v, to_v, new_ver.changes_from_previous
        )

    async def check_regulation_updates(
        self,
        report_id: str
    ) -> list[RegulationUpdate]:
        """检查法规更新"""
        versions = self._versions.get(report_id, [])
        if not versions:
            return []

        latest = versions[-1]
        regulations = latest.content.get("referenced_regulations", [])

        return self.compliance_checker.scan_for_updates(regulations)

    async def get_version_history(self, report_id: str) -> list[dict]:
        """获取版本历史"""
        versions = self._versions.get(report_id, [])

        return [
            {
                "version_id": v.version_id,
                "version_number": v.version_number,
                "content_hash": v.content_hash,
                "created_at": v.created_at.isoformat(),
                "created_by": v.created_by,
                "changes_count": len(v.changes_from_previous),
                "major_changes": sum(1 for c in v.changes_from_previous if c.change_type == ChangeType.MAJOR)
            }
            for v in versions
        ]

    def get_version(self, report_id: str, version_number: str) -> Optional[ReportVersion]:
        """获取特定版本"""
        versions = self._versions.get(report_id, [])
        for v in versions:
            if v.version_number == version_number:
                return v
        return None

    async def auto_update_compliance(
        self,
        report_id: str,
        regulation_update: RegulationUpdate
    ) -> dict:
        """自动更新合规性"""
        version = self.get_version(report_id, "latest")
        if not version:
            return {"success": False, "reason": "Version not found"}

        # 简单实现：标记需要更新
        return {
            "success": True,
            "report_id": report_id,
            "regulation_id": regulation_update.regulation_id,
            "action": f"需要更新 {regulation_update.name} 从 {regulation_update.old_version} 到 {regulation_update.new_version}",
            "impact_level": regulation_update.impact_level
        }


# ============================================================================
# 工厂函数
# ============================================================================

import json

_engine: Optional[ReportEvolutionEngine] = None


def get_evolution_engine() -> ReportEvolutionEngine:
    """获取进化引擎单例"""
    global _engine
    if _engine is None:
        _engine = ReportEvolutionEngine()
    return _engine


async def create_report_version_async(
    report_id: str,
    version_number: str,
    content: dict,
    created_by: str = "system"
) -> ReportVersion:
    """异步创建报告版本"""
    engine = get_evolution_engine()
    return await engine.create_version(report_id, version_number, content, created_by)


async def generate_revision_note_async(
    report_id: str,
    from_version: str = None,
    to_version: str = None
) -> RevisionNote:
    """异步生成修订说明"""
    engine = get_evolution_engine()
    return await engine.generate_revision_note(report_id, from_version, to_version)


async def check_regulation_updates_async(report_id: str) -> list[RegulationUpdate]:
    """异步检查法规更新"""
    engine = get_evolution_engine()
    return await engine.check_regulation_updates(report_id)
