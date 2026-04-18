"""
智能大纲生成器
全学科智能写作助手 - 结构生成模块

功能：
1. 基于文档类型的模板化大纲生成
2. 学科自适应章节结构
3. IMRaD / BP 等标准结构支持
4. 可视化大纲编辑
"""

from typing import Optional, Union
from dataclasses import dataclass, field
from enum import Enum

from writing.intent_detector import DocType, SubjectDomain


class OutlineStyle(Enum):
    """大纲风格"""
    STANDARD = "standard"          # 标准结构
    IMRAD = "imrad"                # IMRaD（论文）
    BP = "business_plan"           # 商业计划书
    SCRIPTS = "scripts"            # 剧本/小说
    MINDMAP = "mindmap"             # 思维导图


@dataclass
class OutlineSection:
    """大纲章节"""
    level: int                    # 层级（1-6）
    title: str                    # 标题
    description: str = ""         # 描述/要点
    content_hints: list[str] = field(default_factory=list)  # 内容提示
    children: list['OutlineSection'] = field(default_factory=list)  # 子章节
    is_expanded: bool = True      # 是否展开
    estimated_words: int = 0      # 预估字数


@dataclass
class OutlineTemplate:
    """大纲模板"""
    name: str
    style: OutlineStyle
    sections: list[OutlineSection]


class OutlineGenerator:
    """
    智能大纲生成器

    支持：
    - 学术论文（IMRaD）
    - 商业计划书
    - 小说/创意写作
    - 技术文档
    - 自定义模板
    """

    # 预定义模板
    TEMPLATES = {
        DocType.ACADEMIC_PAPER: {
            OutlineStyle.IMRAD: [
                OutlineSection(1, "摘要 (Abstract)", "简洁概括研究目的、方法、结果和结论", [
                    "研究背景与目的", "研究方法", "主要发现", "结论与意义"
                ]),
                OutlineSection(1, "引言 (Introduction)", "介绍研究背景和问题"),
                OutlineSection(2, "研究背景", "相关工作综述"),
                OutlineSection(2, "研究问题", "明确要解决的问题"),
                OutlineSection(2, "研究贡献", "本文的主要贡献"),
                OutlineSection(1, "方法 (Methods)", "详细描述研究方法"),
                OutlineSection(2, "实验设计", ""),
                OutlineSection(2, "数据收集", ""),
                OutlineSection(2, "分析方法", ""),
                OutlineSection(1, "结果 (Results)", "呈现研究发现"),
                OutlineSection(1, "讨论 (Discussion)", "分析结果的意义"),
                OutlineSection(2, "结果解释", ""),
                OutlineSection(2, "局限性", ""),
                OutlineSection(2, "未来工作", ""),
                OutlineSection(1, "结论 (Conclusion)", "总结全文"),
                OutlineSection(1, "参考文献", "引用文献列表"),
            ],
            OutlineStyle.STANDARD: [
                OutlineSection(1, "摘要"),
                OutlineSection(1, "引言"),
                OutlineSection(1, "文献综述"),
                OutlineSection(1, "理论框架"),
                OutlineSection(1, "研究方法"),
                OutlineSection(1, "研究结果"),
                OutlineSection(1, "结论与讨论"),
                OutlineSection(1, "参考文献"),
                OutlineSection(1, "附录"),
            ]
        },
        DocType.BUSINESS_PLAN: {
            OutlineStyle.BP: [
                OutlineSection(1, "执行摘要 (Executive Summary)", "1-2页，概述整个BP"),
                OutlineSection(2, "项目简介", ""),
                OutlineSection(2, "市场规模", ""),
                OutlineSection(2, "核心优势", ""),
                OutlineSection(2, "融资需求", ""),
                OutlineSection(1, "问题与痛点", "描述市场存在的问题"),
                OutlineSection(1, "解决方案", "产品/服务如何解决问题"),
                OutlineSection(1, "市场分析", "TAM/SAM/SOM 分析"),
                OutlineSection(2, "目标市场", ""),
                OutlineSection(2, "用户画像", ""),
                OutlineSection(2, "竞争分析", ""),
                OutlineSection(1, "商业模式", "如何盈利"),
                OutlineSection(2, "收入模型", ""),
                OutlineSection(2, "定价策略", ""),
                OutlineSection(1, "运营计划", ""),
                OutlineSection(1, "团队介绍", ""),
                OutlineSection(1, "财务预测", "3-5年财务预测"),
                OutlineSection(2, "收入预测", ""),
                OutlineSection(2, "成本结构", ""),
                OutlineSection(2, "盈亏平衡点", ""),
                OutlineSection(1, "融资计划", ""),
                OutlineSection(1, "风险与退出", ""),
            ]
        },
        DocType.BUSINESS_REPORT: {
            OutlineStyle.STANDARD: [
                OutlineSection(1, "报告摘要", "核心发现和建议"),
                OutlineSection(1, "背景介绍", "报告目的和范围"),
                OutlineSection(1, "方法论", "数据来源和分析方法"),
                OutlineSection(1, "主要发现", ""),
                OutlineSection(2, "发现一", ""),
                OutlineSection(2, "发现二", ""),
                OutlineSection(2, "发现三", ""),
                OutlineSection(1, "分析和建议", ""),
                OutlineSection(1, "结论", ""),
                OutlineSection(1, "附录", "数据和表格"),
            ]
        },
        DocType.NOVEL: {
            OutlineStyle.SCRIPTS: [
                OutlineSection(1, "世界观设定", "故事背景和规则"),
                OutlineSection(2, "时代背景", ""),
                OutlineSection(2, "地点设定", ""),
                OutlineSection(2, "特殊规则", ""),
                OutlineSection(1, "人物设定", "主要角色介绍"),
                OutlineSection(2, "主角", "姓名、背景、性格、目标"),
                OutlineSection(2, "配角", ""),
                OutlineSection(2, "反派", ""),
                OutlineSection(1, "故事主线", ""),
                OutlineSection(2, "第一幕：建置", "介绍世界和主角"),
                OutlineSection(2, "第二幕：对抗", "冲突和挑战"),
                OutlineSection(2, "第三幕：解决", "高潮和结局"),
                OutlineSection(1, "章节大纲", "各章节概要"),
            ]
        },
        DocType.TECHNICAL_DOC: {
            OutlineStyle.STANDARD: [
                OutlineSection(1, "概述", "文档目的和范围"),
                OutlineSection(2, "背景", ""),
                OutlineSection(2, "目标读者", ""),
                OutlineSection(1, "快速开始", "5分钟上手指南"),
                OutlineSection(2, "前置要求", ""),
                OutlineSection(2, "安装步骤", ""),
                OutlineSection(2, "运行示例", ""),
                OutlineSection(1, "核心概念", ""),
                OutlineSection(1, "详细教程", ""),
                OutlineSection(1, "API 参考", ""),
                OutlineSection(2, "函数/方法", ""),
                OutlineSection(2, "参数说明", ""),
                OutlineSection(1, "最佳实践", ""),
                OutlineSection(1, "故障排除", ""),
                OutlineSection(1, "版本历史", ""),
            ]
        },
    }

    # 学科特定章节
    SUBJECT_SPECIFIC = {
        SubjectDomain.PHYSICS: [
            OutlineSection(2, "物理模型", "理论模型和假设"),
            OutlineSection(2, "公式推导", "核心公式和推导过程"),
        ],
        SubjectDomain.ECONOMICS: [
            OutlineSection(2, "经济学模型", "理论框架"),
            OutlineSection(2, "数据分析", "统计和经济分析"),
        ],
        SubjectDomain.COMPUTER_SCIENCE: [
            OutlineSection(2, "算法设计", ""),
            OutlineSection(2, "系统架构", ""),
            OutlineSection(2, "复杂度分析", ""),
        ],
    }

    def __init__(self):
        self._current_template: Optional[OutlineTemplate] = None
        self._custom_sections: list[OutlineSection] = []

    def set_template(self, doc_type: DocType, subject: SubjectDomain = None):
        """设置模板"""
        templates = self.TEMPLATES.get(doc_type, self.TEMPLATES[DocType.GENERAL])
        style = list(templates.keys())[0]
        sections = templates[style]

        # 添加学科特定章节
        if subject and subject in self.SUBJECT_SPECIFIC:
            sections = self._insert_subject_sections(sections, subject)

        self._current_template = OutlineTemplate(
            name=f"{doc_type.value}_{style.value}",
            style=style,
            sections=sections
        )

    def generate(self, topic: str, doc_type: DocType = None, subject: SubjectDomain = None,
                  style: OutlineStyle = None) -> list[OutlineSection]:
        """
        生成大纲

        Args:
            topic: 主题
            doc_type: 文档类型
            subject: 学科领域
            style: 大纲风格

        Returns:
            list[OutlineSection]: 章节列表
        """
        # 获取模板
        if doc_type:
            templates = self.TEMPLATES.get(doc_type)
            if templates:
                if style and style in templates:
                    sections = templates[style]
                else:
                    sections = list(templates.values())[0]

                # 添加学科特定章节
                if subject and subject in self.SUBJECT_SPECIFIC:
                    sections = self._insert_subject_sections(sections, subject)

                # 替换主题占位符
                return self._replace_placeholders(sections, topic)
            else:
                return self._generate_generic(topic)

        return self._generate_generic(topic)

    def generate_from_keywords(self, keywords: list[str]) -> list[OutlineSection]:
        """
        基于关键词生成大纲

        Args:
            keywords: 关键词列表

        Returns:
            list[OutlineSection]: 生成的大纲
        """
        # 简单实现 - 实际应该用 AI 分析关键词关系
        sections = []

        for i, kw in enumerate(keywords[:5]):
            sections.append(OutlineSection(
                level=1,
                title=f"关于 {kw} 的分析",
                content_hints=[f"展开 {kw} 的定义", f"讨论 {kw} 的影响"]
            ))

        return sections

    def _generate_generic(self, topic: str) -> list[OutlineSection]:
        """生成通用大纲"""
        return [
            OutlineSection(1, topic, "主要内容"),
            OutlineSection(2, "背景介绍", ""),
            OutlineSection(2, "核心内容", ""),
            OutlineSection(2, "深入分析", ""),
            OutlineSection(2, "总结", ""),
        ]

    def _insert_subject_sections(self, sections: list[OutlineSection], subject: SubjectDomain) -> list[OutlineSection]:
        """插入学科特定章节"""
        subject_sections = self.SUBJECT_SPECIFIC.get(subject, [])

        if not subject_sections:
            return sections

        # 找到合适的位置插入（在方法或理论章节之后）
        result = []
        method_found = False

        for section in sections:
            result.append(section)
            if '方法' in section.title or '理论' in section.title:
                result.extend(subject_sections)
                method_found = True

        if not method_found and subject_sections:
            # 插入到中间位置
            mid = len(result) // 2
            result = result[:mid] + subject_sections + result[mid:]

        return result

    def _replace_placeholders(self, sections: list[OutlineSection], topic: str) -> list[OutlineSection]:
        """替换占位符"""
        result = []

        for section in sections:
            new_section = OutlineSection(
                level=section.level,
                title=section.title,
                description=section.description.replace("{topic}", topic),
                content_hints=[h.replace("{topic}", topic) for h in section.content_hints],
                children=self._replace_placeholders(section.children, topic),
            )
            result.append(new_section)

        return result

    def to_markdown(self, sections: list[OutlineSection], indent: str = "") -> str:
        """
        转换为 Markdown 格式

        Args:
            sections: 章节列表
            indent: 缩进

        Returns:
            str: Markdown 文本
        """
        lines = []

        for section in sections:
            # 标题
            level = min(section.level, 6)
            lines.append(f"{indent}{'#' * level} {section.title}")

            # 描述
            if section.description:
                lines.append(f"{indent}{section.description}")

            # 子章节
            if section.children:
                lines.append(self.to_markdown(section.children, indent + "  "))

        return "\n".join(lines)

    def to_json(self, sections: list[OutlineSection]) -> list[dict]:
        """
        转换为 JSON 结构

        Args:
            sections: 章节列表

        Returns:
            list[dict]: JSON 兼容的结构
        """
        result = []

        for section in sections:
            result.append({
                "level": section.level,
                "title": section.title,
                "description": section.description,
                "content_hints": section.content_hints,
                "children": self.to_json(section.children) if section.children else [],
                "is_expanded": section.is_expanded,
                "estimated_words": section.estimated_words,
            })

        return result

    def from_json(self, data: list[dict]) -> list[OutlineSection]:
        """
        从 JSON 恢复

        Args:
            data: JSON 数据

        Returns:
            list[OutlineSection]: 章节列表
        """
        sections = []

        for item in data:
            section = OutlineSection(
                level=item.get("level", 1),
                title=item.get("title", ""),
                description=item.get("description", ""),
                content_hints=item.get("content_hints", []),
                children=self.from_json(item.get("children", [])),
                is_expanded=item.get("is_expanded", True),
                estimated_words=item.get("estimated_words", 0),
            )
            sections.append(section)

        return sections


# 单例
_generator: Optional[OutlineGenerator] = None


def get_outline_generator() -> OutlineGenerator:
    """获取大纲生成器单例"""
    global _generator
    if _generator is None:
        _generator = OutlineGenerator()
    return _generator
