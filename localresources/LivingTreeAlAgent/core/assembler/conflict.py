"""
战术评估 (Tactical Assessment)

目标：提前预警与内置功能重叠，防运行时打架。

对比维度：
- 能力标签（如 pdf_extract）
- 端口占用
- 环境变量

输出冲突报告
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ConflictType(Enum):
    """冲突类型"""
    CAPABILITY_OVERLAP = "capability_overlap"     # 能力重叠
    PORT_CONFLICT = "port_conflict"               # 端口占用
    ENV_VAR_CONFLICT = "env_var_conflict"         # 环境变量冲突
    DEPENDENCY_CONFLICT = "dependency_conflict"  # 依赖冲突
    NONE = "none"


class ResolutionStrategy(Enum):
    """解决策略"""
    COEXIST = "coexist"           # 并行共存（路由优先新工具，可切换）
    REPLACE = "replace"           # 替换旧版（禁用内置，全切新工具）
    CANCEL = "cancel"             # 取消装配（放弃安装）


@dataclass
class BuiltinCapability:
    """内置能力"""
    name: str
    tags: list[str]
    description: str = ""
    module: str = ""


@dataclass
class ConflictReport:
    """冲突报告"""
    has_conflict: bool = False
    conflicts: list['ConflictItem'] = field(default_factory=list)

    # 汇总信息
    summary: str = ""
    recommended_strategy: ResolutionStrategy = ResolutionStrategy.COEXIST

    def add_conflict(
        self,
        conflict_type: ConflictType,
        builtin: BuiltinCapability,
        external: str,
        severity: str = "medium"
    ):
        """添加冲突项"""
        self.has_conflict = True
        self.conflicts.append(ConflictItem(
            conflict_type=conflict_type,
            builtin=builtin,
            external=external,
            severity=severity
        ))

    def to_dict(self) -> dict:
        return {
            "has_conflict": self.has_conflict,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "summary": self.summary,
            "recommended_strategy": self.recommended_strategy.value,
        }


@dataclass
class ConflictItem:
    """冲突项"""
    conflict_type: ConflictType
    builtin: BuiltinCapability
    external: str
    severity: str = "medium"  # low / medium / high / critical

    # 详情
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "conflict_type": self.conflict_type.value,
            "builtin": {
                "name": self.builtin.name,
                "tags": self.builtin.tags,
                "description": self.builtin.description,
            },
            "external": self.external,
            "severity": self.severity,
            "details": self.details,
        }


class ConflictDetector:
    """战术评估 - 冲突检测"""

    # 内置能力注册表
    BUILTIN_CAPABILITIES: list[BuiltinCapability] = [
        # 文档解析
        BuiltinCapability(
            name="builtin_pdf",
            tags=["pdf", "pdf_extract", "pdf_parser", "pdf_reader"],
            description="内置 PDF 解析器",
            module="core.document_parser"
        ),
        BuiltinCapability(
            name="builtin_excel",
            tags=["excel", "xlsx", "csv", "spreadsheet", "xls"],
            description="内置 Excel/CSV 解析器",
            module="core.document_parser"
        ),
        BuiltinCapability(
            name="builtin_doc",
            tags=["doc", "docx", "word", "office"],
            description="内置 Word 文档解析",
            module="core.document_parser"
        ),

        # 网络相关
        BuiltinCapability(
            name="builtin_http",
            tags=["http", "https", "request", "fetch", "web_request"],
            description="内置 HTTP 请求",
            module="core.network"
        ),
        BuiltinCapability(
            name="builtin_websocket",
            tags=["websocket", "ws", "socket", "realtime"],
            description="内置 WebSocket",
            module="core.network"
        ),

        # AI/ML
        BuiltinCapability(
            name="builtin_llm",
            tags=["llm", "gpt", "openai", "chat", "ai", "model"],
            description="内置 LLM 接口",
            module="core.llm_client"
        ),
        BuiltinCapability(
            name="builtin_embedding",
            tags=["embedding", "vector", "embed", "similarity"],
            description="内置 Embedding 服务",
            module="core.embedding"
        ),

        # 数据处理
        BuiltinCapability(
            name="builtin_json",
            tags=["json", "parse", "serialize", "yaml", "toml"],
            description="内置配置解析",
            module="core.config"
        ),
        BuiltinCapability(
            name="builtin_storage",
            tags=["storage", "db", "database", "sqlite", "persist"],
            description="内置存储",
            module="core.storage"
        ),

        # 媒体处理
        BuiltinCapability(
            name="builtin_image",
            tags=["image", "img", "picture", "thumbnail"],
            description="内置图片处理",
            module="core.media"
        ),
        BuiltinCapability(
            name="builtin_audio",
            tags=["audio", "sound", "music", "mp3", "wav"],
            description="内置音频处理",
            module="core.media"
        ),

        # 压缩/加密
        BuiltinCapability(
            name="builtin_zip",
            tags=["zip", "compress", "archive", "unzip", "tar"],
            description="内置压缩/解压",
            module="core.utils"
        ),
        BuiltinCapability(
            name="builtin_crypto",
            tags=["crypto", "encrypt", "decrypt", "hash", "signature"],
            description="内置加密工具",
            module="core.security"
        ),
    ]

    def __init__(self):
        self._capability_index: dict[str, BuiltinCapability] = {}
        self._build_index()

    def _build_index(self):
        """构建能力索引"""
        for cap in self.BUILTIN_CAPABILITIES:
            for tag in cap.tags:
                self._capability_index[tag.lower()] = cap

    def detect(self, external_tags: list[str], external_name: str = "") -> ConflictReport:
        """
        检测冲突

        Args:
            external_tags: 外部库的能力标签
            external_name: 外部库名称

        Returns:
            ConflictReport: 冲突报告
        """
        report = ConflictReport()

        for tag in external_tags:
            tag_lower = tag.lower()

            # 检查能力重叠
            if tag_lower in self._capability_index:
                builtin = self._capability_index[tag_lower]
                report.add_conflict(
                    ConflictType.CAPABILITY_OVERLAP,
                    builtin,
                    external_name,
                    severity=self._assess_severity(tag_lower, builtin)
                )

        # 生成汇总
        if report.has_conflict:
            report.summary = self._generate_summary(report)
            report.recommended_strategy = self._recommend_strategy(report)

        return report

    def check_builtin_capability(self, capability_name: str) -> Optional[BuiltinCapability]:
        """检查内置能力是否存在"""
        for cap in self.BUILTIN_CAPABILITIES:
            if cap.name == capability_name:
                return cap
        return None

    def _assess_severity(self, tag: str, builtin: BuiltinCapability) -> str:
        """评估冲突严重程度"""
        # 高危：核心功能重叠
        high_risk_tags = {'llm', 'gpt', 'crypto', 'encrypt', 'auth', 'jwt'}
        if tag in high_risk_tags:
            return "high"

        # 中危：常见功能
        medium_risk_tags = {'pdf', 'json', 'http', 'websocket', 'database'}
        if tag in medium_risk_tags:
            return "medium"

        return "low"

    def _generate_summary(self, report: ConflictReport) -> str:
        """生成冲突汇总"""
        summaries = []

        overlap_count = sum(
            1 for c in report.conflicts
            if c.conflict_type == ConflictType.CAPABILITY_OVERLAP
        )

        if overlap_count > 0:
            builtin_names = list(set(
                c.builtin.name for c in report.conflicts
                if c.conflict_type == ConflictType.CAPABILITY_OVERLAP
            ))
            summaries.append(f"检测到 {overlap_count} 处能力重叠:")
            for name in builtin_names:
                summaries.append(f"  - {name}")

        return "\n".join(summaries) if summaries else "无冲突"

    def _recommend_strategy(self, report: ConflictReport) -> ResolutionStrategy:
        """推荐解决策略"""
        # 有高危冲突：建议共存
        if any(c.severity == "high" for c in report.conflicts):
            return ResolutionStrategy.COEXIST

        # 有中危冲突：可以替换
        if any(c.severity == "medium" for c in report.conflicts):
            return ResolutionStrategy.COEXIST  # 默认共存，让用户选择

        return ResolutionStrategy.COEXIST

    def format_report_display(self, report: ConflictReport) -> str:
        """格式化冲突报告为显示文本"""
        if not report.has_conflict:
            return "✅ **战术评估：通过**\n未检测到冲突，可直接装配。"

        lines = ["⚠️ **战术评估：检测到冲突**\n"]

        for i, conflict in enumerate(report.conflicts, 1):
            severity_icon = {
                "low": "🟢",
                "medium": "🟡",
                "high": "🟠",
                "critical": "🔴"
            }.get(conflict.severity, "⚪")

            lines.append(f"{i}. {severity_icon} **{conflict.conflict_type.value}**")
            lines.append(f"   内置: {conflict.builtin.name}")
            lines.append(f"   外部: {conflict.external}")
            lines.append(f"   标签: {', '.join(conflict.builtin.tags)}")

        lines.append("")
        lines.append(f"📋 **建议策略**: {report.recommended_strategy.value}")
        lines.append(f"\n{report.summary}")

        return "\n".join(lines)

    def get_resolution_options(self) -> list[dict]:
        """获取解决选项"""
        return [
            {
                "strategy": ResolutionStrategy.COEXIST.value,
                "icon": "✅",
                "title": "并行共存",
                "description": "保留内置模块，新增外部库作为补充。路由优先使用新工具，用户可随时切换。",
                "risk": "low"
            },
            {
                "strategy": ResolutionStrategy.REPLACE.value,
                "icon": "🔄",
                "title": "替换旧版",
                "description": "禁用内置模块，全面切换到新外部库。适用于新库功能明显优于内置的情况。",
                "risk": "medium"
            },
            {
                "strategy": ResolutionStrategy.CANCEL.value,
                "icon": "❌",
                "title": "取消装配",
                "description": "放弃安装该外部库，继续使用现有内置模块。",
                "risk": "none"
            }
        ]