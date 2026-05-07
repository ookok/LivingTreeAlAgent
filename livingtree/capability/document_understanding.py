"""DocumentUnderstanding — LLM驱动的语义文档理解（非模板变量替换）.

核心理念：文档不是填空题，是需要专家阅读、理解、质疑、建议的知识载体.

与 document_intelligence.py 的关系：
  document_intelligence → 结构提取（段落/样式/表格）——"看得见"
  document_understanding  → 语义理解（含义/矛盾/缺口/建议）——"看得懂"

五维分析：
  1. 结构理解 — 每节干什么（方法？数据？结论？合规？）
  2. 跨章节验证 — 第5章的结论和第3章的数据矛盾吗？
  3. 法规缺口 — 根据GB标准，报告还缺什么？
  4. 数值校验 — 排放量计算对吗？限值超标了吗？
  5. 专家建议 — 以环评专家视角，这报告怎么改进？

Usage:
    du = DocumentUnderstanding(consciousness=llm)
    findings = await du.analyze("环评报告.docx")
    for f in findings:
        print(f"{f.severity}: {f.message}")
    # → [CRITICAL] 第3.2节SO2数据与第5章结论矛盾
    # → [WARNING] 缺少GB3096-2008噪声标准引用
    # → [SUGGEST] 建议在第4章增加扩散模型参数说明
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger


# ═══════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════

class FindingSeverity(str, Enum):
    CRITICAL = "critical"     # 致命问题，必须修改
    WARNING = "warning"       # 需要关注
    SUGGESTION = "suggestion" # 改进建议
    INFO = "info"             # 信息性


@dataclass
class Finding:
    """文档分析发现."""
    severity: FindingSeverity
    category: str              # consistency / gap / numeric / structure / compliance
    section: str = ""           # 涉及章节
    message: str = ""
    evidence: str = ""          # 原文引用
    suggestion: str = ""        # 修复建议
    confidence: float = 0.7

    def one_line(self) -> str:
        icon = {"critical": "🔴", "warning": "🟡", "suggestion": "💡", "info": "ℹ️"}
        return f"{icon.get(self.severity.value, '')} [{self.section}] {self.message}"


@dataclass
class SectionPurpose:
    """章节用途分类结果."""
    section_id: str
    title: str = ""
    purpose: str = ""           # methodology / data_presentation / analysis / conclusion / compliance / appendix
    key_entities: list[str] = field(default_factory=list)
    key_numbers: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # 引用的其他章节
    summary: str = ""


@dataclass
class DocumentAnalysis:
    """完整文档语义分析结果."""
    filepath: str = ""
    section_purposes: list[SectionPurpose] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    overall_score: float = 0.0        # 0-100
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)
    tokens_used: int = 0

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == FindingSeverity.CRITICAL)

    @property
    def report(self) -> str:
        lines = [f"# 文档分析报告: {Path(self.filepath).name}", "",
                 f"**综合评分**: {self.overall_score:.0f}/100",
                 f"**发现**: {len(self.findings)} 条 ({self.critical_count} 致命)", ""]
        for f in self.findings:
            lines.append(f"- {f.one_line()}")
        if self.recommendations:
            lines.append("")
            lines.append("## 改进建议")
            for r in self.recommendations:
                lines.append(f"- {r}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Document Understanding Engine
# ═══════════════════════════════════════════════════════════════════

class DocumentUnderstanding:
    """LLM驱动的语义文档理解——真正"读懂"文档，而非模板填充.

    委托 LLM consciousness 执行五项分析，聚合结果。
    """

    # 环评报告章节模式
    EIA_SECTION_PATTERNS: dict[str, str] = {
        "总则|概述|前言|引言": "context — 项目背景和编制依据",
        "工程分析|工艺流程|生产": "methodology — 生产工艺和污染源分析",
        "环境现状|监测|调查": "data_presentation — 环境质量现状数据",
        "影响预测|扩散|模型": "analysis — 环境影响预测与评价",
        "防治措施|对策|减缓": "compliance — 污染防治措施",
        "结论|总结|建议": "conclusion — 评价结论与建议",
        "附录|附件": "appendix — 补充材料",
    }

    # GB标准知识（内嵌，LLM验证时参考）
    GB_STANDARDS: dict[str, str] = {
        "GB3095-2012": "环境空气质量标准 — SO2/NO2/PM2.5/PM10/CO/O3限值",
        "GB3096-2008": "声环境质量标准 — 各类功能区噪声限值",
        "GB3838-2002": "地表水环境质量标准 — COD/BOD/NH3-N等限值",
        "HJ2.2-2018": "大气环境影响评价技术导则 — AERSCREEN/ADMS/CALPUFF模型要求",
        "HJ2.4-2022": "声环境影响评价技术导则",
        "GB16297-1996": "大气污染物综合排放标准",
        "GB8978-1996": "污水综合排放标准",
    }

    def __init__(self, consciousness: Any = None):
        self._consciousness = consciousness
        self._analysis_count = 0

    async def analyze(self, filepath: str, domain: str = "environmental") -> DocumentAnalysis:
        """对文档进行完整的语义理解分析.

        Args:
            filepath: 文档路径
            domain: 领域 (environmental / legal / general)

        Returns:
            DocumentAnalysis with all findings
        """
        self._analysis_count += 1
        analysis = DocumentAnalysis(filepath=filepath)

        # Step 0: 读取文档结构
        structure = self._read_structure(filepath)
        if not structure:
            analysis.summary = "无法读取文档"
            return analysis

        sections = structure.get("sections", [])
        analysis.section_purposes = await self._classify_sections(sections, domain)
        total_tokens = 2000  # Section classification estimate

        # Step 1: 跨章节一致性验证
        consistency = await self._validate_consistency(sections, analysis.section_purposes, domain)
        analysis.findings.extend(consistency)
        total_tokens += 3000

        # Step 2: 法规缺口检测
        if domain == "environmental":
            gaps = await self._detect_gaps(sections, analysis.section_purposes)
            analysis.findings.extend(gaps)
            total_tokens += 3000

        # Step 3: 数值一致性校验
        numeric_issues = self._validate_numerics(sections, analysis.section_purposes)
        analysis.findings.extend(numeric_issues)

        # Step 4: 专家整体评审
        critique = await self._expert_critique(sections, domain, analysis.findings)
        analysis.recommendations = critique.get("recommendations", [])
        analysis.summary = critique.get("summary", "")
        analysis.overall_score = critique.get("score", 60.0)
        total_tokens += 4000

        analysis.tokens_used = total_tokens
        logger.info(
            f"DocumentUnderstanding: {Path(filepath).name} → "
            f"score={analysis.overall_score:.0f}/100, "
            f"{len(analysis.findings)} findings ({analysis.critical_count} critical)")
        return analysis

    # ═══ Step 0: 结构读取 ═══

    def _read_structure(self, filepath: str) -> dict | None:
        """读取文档结构（委托 document_intelligence）."""
        try:
            from .document_intelligence import get_doc_intelligence
            di = get_doc_intelligence()
            ws = di.read_docx(filepath)
            # 按标题划分章节
            sections: list[dict] = []
            current_section: dict = {"title": "开头", "paragraphs": []}
            for p in ws.paragraphs:
                style = p.get("style", "")
                if "Heading" in style or "标题" in style:
                    if current_section["paragraphs"]:
                        sections.append(current_section)
                    current_section = {"title": p.get("text", "")[:80], "paragraphs": [p]}
                else:
                    current_section["paragraphs"].append(p)
            if current_section["paragraphs"]:
                sections.append(current_section)
            return {"sections": sections, "tables": ws.tables, "metadata": ws.metadata}
        except Exception as e:
            logger.debug(f"_read_structure: {e}")
            return None

    # ═══ Step 1: 章节用途分类 ═══

    async def _classify_sections(
        self, sections: list[dict], domain: str,
    ) -> list[SectionPurpose]:
        """LLM 分析每章——它是在陈述数据，还是在下结论？"""
        purposes = []
        for i, sec in enumerate(sections):
            title = sec.get("title", f"section_{i}")
            text_sample = "\n".join(
                p.get("text", "") for p in sec.get("paragraphs", [])[:5])[:500]

            # 先尝试模式匹配
            purpose = self._match_section_pattern(title)

            # LLM 精炼
            if self._consciousness and purpose == "unknown":
                purpose = await self._llm_classify_section(title, text_sample, domain)

            key_entities = self._extract_entities(text_sample)
            key_numbers = self._extract_numbers(text_sample)

            purposes.append(SectionPurpose(
                section_id=f"s{i+1}",
                title=title[:60],
                purpose=purpose,
                key_entities=key_entities,
                key_numbers=key_numbers,
                summary=text_sample[:200],
            ))
        return purposes

    def _match_section_pattern(self, title: str) -> str:
        for pattern, purpose in self.EIA_SECTION_PATTERNS.items():
            if re.search(pattern, title):
                return purpose
        return "unknown"

    async def _llm_classify_section(
        self, title: str, text: str, domain: str,
    ) -> str:
        try:
            prompt = (
                f"Classify this document section by its PURPOSE (not content):\n"
                f"Title: {title}\n"
                f"Sample: {text[:300]}\n\n"
                f"Choose ONE: methodology, data_presentation, analysis, "
                f"conclusion, compliance, context, appendix. Return only the word."
            )
            raw = await self._consciousness.query(prompt, max_tokens=50, temperature=0.1)
            return raw.strip().lower()
        except Exception:
            return "unknown"

    # ═══ Step 2: 跨章节一致性验证 ═══

    async def _validate_consistency(
        self, sections: list[dict], purposes: list[SectionPurpose], domain: str,
    ) -> list[Finding]:
        """LLM检测：第5章的结论和第3章的数据是否矛盾？"""
        findings: list[Finding] = []

        # 找出结论章节和数据章节
        conclusion_secs = [p for p in purposes if "conclusion" in p.purpose]
        data_secs = [p for p in purposes if "data_presentation" in p.purpose or "analysis" in p.purpose]

        if not conclusion_secs or not data_secs:
            return findings

        # 为每对结论-数据章节构造验证
        for conc in conclusion_secs[:2]:
            for data in data_secs[:2]:
                conc_text = self._get_section_text(sections, conc.section_id)
                data_text = self._get_section_text(sections, data.section_id)

                if not conc_text or not data_text or not self._consciousness:
                    continue

                finding = await self._llm_check_consistency(
                    conc.section_id, conc_text,
                    data.section_id, data_text,
                )
                if finding:
                    findings.append(finding)

        return findings

    async def _llm_check_consistency(
        self, conc_id: str, conc_text: str, data_id: str, data_text: str,
    ) -> Finding | None:
        try:
            prompt = (
                f"Check if the CONCLUSION section's claims are supported by the DATA section.\n\n"
                f"=== CONCLUSION ({conc_id}) ===\n{conc_text[:1000]}\n\n"
                f"=== DATA ({data_id}) ===\n{data_text[:1000]}\n\n"
                f"Output JSON:\n"
                f'{{"consistent": true/false, '
                f'"issue": "具体矛盾（无则空）", '
                f'"evidence_data": "数据章节的原文引用", '
                f'"evidence_conclusion": "结论章节的原文引用", '
                f'"severity": "critical/warning/suggestion"}}'
            )
            raw = await self._consciousness.query(prompt, max_tokens=400, temperature=0.2)
            data = self._parse_json(raw)
            if data and not data.get("consistent"):
                return Finding(
                    severity=FindingSeverity(data.get("severity", "warning")),
                    category="consistency",
                    section=f"{conc_id} ↔ {data_id}",
                    message=data.get("issue", "结论与数据不一致"),
                    evidence=data.get("evidence_data", ""),
                    suggestion=f"建议修改{conc_id}或补充{data_id}中的支撑数据",
                    confidence=0.8,
                )
        except Exception as e:
            logger.debug(f"consistency check: {e}")
        return None

    # ═══ Step 3: 法规缺口检测 ═══

    async def _detect_gaps(
        self, sections: list[dict], purposes: list[SectionPurpose],
    ) -> list[Finding]:
        """检测文档是否遗漏了必要的法规引用和标准符合性说明."""
        findings: list[Finding] = []

        full_text = "\n".join(
            self._get_section_text(sections, p.section_id) or ""
            for p in purposes)[:8000]

        # 检查每个GB标准是否被引用
        for std_id, std_desc in self.GB_STANDARDS.items():
            std_base = std_id.split("-")[0]
            if std_id not in full_text and std_base not in full_text:
                findings.append(Finding(
                    severity=FindingSeverity.WARNING,
                    category="gap",
                    section="全文",
                    message=f"缺少 {std_id} ({std_desc}) 的引用或符合性说明",
                    suggestion=f"建议在第1章或第2章增加 {std_id} 作为编制依据之一",
                ))

        # LLM 检测更多缺口
        if self._consciousness:
            llm_gaps = await self._llm_detect_gaps(full_text)
            findings.extend(llm_gaps)

        return findings

    async def _llm_detect_gaps(self, text: str) -> list[Finding]:
        try:
            prompt = (
                f"As an environmental impact assessment expert, review this report "
                f"and identify MISSING content that is required by Chinese regulations.\n\n"
                f"Report excerpt:\n{text[:4000]}\n\n"
                f"Output JSON array:\n"
                f'[{{"missing": "缺失内容", "regulation": "相关法规", '
                f'"severity": "critical/warning/suggestion", '
                f'"suggestion": "补充建议"}}]'
            )
            raw = await self._consciousness.query(prompt, max_tokens=500, temperature=0.2)
            data = self._parse_json(raw)
            if isinstance(data, list):
                return [
                    Finding(
                        severity=FindingSeverity(d.get("severity", "warning")),
                        category="gap",
                        message=d.get("missing", ""),
                        evidence=d.get("regulation", ""),
                        suggestion=d.get("suggestion", ""),
                    )
                    for d in data[:5] if d.get("missing")
                ]
        except Exception as e:
            logger.debug(f"gap detection: {e}")
        return []

    # ═══ Step 4: 数值一致性 ═══

    def _validate_numerics(
        self, sections: list[dict], purposes: list[SectionPurpose],
    ) -> list[Finding]:
        """启发式数值校验：数据章节的值是否超标？."""
        findings: list[Finding] = []

        # 提取所有带单位的数值
        all_numbers = []
        for p in purposes:
            for num_str in p.key_numbers:
                all_numbers.append((p.section_id, num_str))

        # 检测明显的超标（>限值的数值）
        limits = {
            "SO2": 500, "NO2": 200, "PM2.5": 75, "PM10": 150,
            "CO": 10, "O3": 200,  # μg/m³, GB3095-2012 二级标准
        }
        for sec_id, num_str in all_numbers:
            for pollutant, limit in limits.items():
                if pollutant.lower() in num_str.lower():
                    try:
                        val = float(re.findall(r'[\d.]+', num_str)[0])
                        if val > limit:
                            findings.append(Finding(
                                severity=FindingSeverity.CRITICAL if val > limit * 2 else FindingSeverity.WARNING,
                                category="numeric",
                                section=sec_id,
                                message=f"{pollutant}排放值 {val} 超过 {pollutant}限值 {limit}",
                                suggestion=f"请核实数据或补充超标原因说明",
                            ))
                    except (ValueError, IndexError):
                        pass

        return findings

    # ═══ Step 5: 专家评审 ═══

    async def _expert_critique(
        self, sections: list[dict], domain: str, existing_findings: list[Finding],
    ) -> dict:
        """LLM 作为领域专家给出综合评审."""
        if not self._consciousness:
            return {"score": 60, "summary": "无LLM，无法评审",
                    "recommendations": []}

        outline = "\n".join(
            f"- {s.get('title', '')[:60]}" for s in sections[:15])
        known_issues = "\n".join(f"- {f.one_line()}" for f in existing_findings[:10])

        try:
            prompt = (
                f"As a senior {domain} expert, review this document outline.\n\n"
                f"=== Document Outline ===\n{outline}\n\n"
                f"=== Known Issues ===\n{known_issues or 'None detected'}\n\n"
                f"Provide an expert assessment:\n"
                f"1. Overall quality score (0-100)\n"
                f"2. Summary (2-3 sentences in Chinese)\n"
                f"3. Top 3-5 actionable recommendations\n\n"
                f"Output JSON:\n"
                f'{{"score": 0-100, "summary": "综合评语", '
                f'"recommendations": ["建议1", "建议2"]}}'
            )
            raw = await self._consciousness.query(prompt, max_tokens=500, temperature=0.4)
            data = self._parse_json(raw)
            if data:
                return data
        except Exception as e:
            logger.debug(f"expert critique: {e}")

        return {"score": 60, "summary": "评审未能完成",
                "recommendations": []}

    # ═══ Helpers ═══

    def _get_section_text(self, sections: list[dict], section_id: str) -> str | None:
        idx = int(section_id[1:]) - 1 if section_id.startswith("s") else -1
        if 0 <= idx < len(sections):
            return "\n".join(
                p.get("text", "") for p in sections[idx].get("paragraphs", []))
        return None

    @staticmethod
    def _extract_entities(text: str) -> list[str]:
        """提取关键实体."""
        entities = []
        # 标准编号
        found = re.findall(r'[A-Z]{2,}\d+[\d.-]*', text)
        entities.extend(found)
        # 中文法规
        found = re.findall(r'《[^》]+》', text)
        entities.extend(found)
        # 污染物名称
        for kw in ["SO2", "NO2", "PM2.5", "PM10", "CO", "O3",
                    "COD", "BOD", "NH3-N", "TSP", "VOCs"]:
            if kw in text:
                entities.append(kw)
        return list(set(entities))[:10]

    @staticmethod
    def _extract_numbers(text: str) -> list[str]:
        """提取带单位的数值."""
        found = re.findall(r'\d+\.?\d*\s*(?:mg/m³|μg/m³|dB|t/a|m³/h|kg/h|mg/L)', text)
        return found[:10]

    @staticmethod
    def _parse_json(raw: str) -> Any:
        try:
            if "```json" in raw:
                s = raw.index("```json") + 7
                e = raw.index("```", s)
                raw = raw[s:e]
            elif "```" in raw:
                s = raw.index("```") + 3
                e = raw.index("```", s)
                raw = raw[s:e]
            raw = raw.strip()
            if raw.startswith("{") or raw.startswith("["):
                return json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            pass
        return None


# ── Singleton ──────────────────────────────────────────────────────

_doc_understanding: DocumentUnderstanding | None = None


def get_doc_understanding(consciousness: Any = None) -> DocumentUnderstanding:
    global _doc_understanding
    if _doc_understanding is None:
        _doc_understanding = DocumentUnderstanding(consciousness=consciousness)
    elif consciousness and not _doc_understanding._consciousness:
        _doc_understanding._consciousness = consciousness
    return _doc_understanding
