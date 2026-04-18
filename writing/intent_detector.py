"""
智能意图识别系统
全学科智能写作助手 - 入口模块

功能：
1. 多模态输入识别（文件/对话/拖拽）
2. 文档类型自动检测（小说/报告/论文）
3. 学科领域分类
4. 置信度反馈
"""

import re
import json
from pathlib import Path
from typing import Optional, TypedDict
from dataclasses import dataclass, field
from enum import Enum
import mimetypes


class DocType(Enum):
    """文档类型枚举"""
    UNKNOWN = "unknown"
    GENERAL = "general"                    # 通用
    ACADEMIC_PAPER = "academic_paper"      # 学术论文
    BUSINESS_REPORT = "business_report"   # 商业报告
    BUSINESS_PLAN = "business_plan"        # 商业计划书
    NOVEL = "novel"                        # 小说/创意写作
    TECHNICAL_DOC = "technical_doc"       # 技术文档
    BLOG = "blog"                          # 博客/文章
    EMAIL = "email"                        # 邮件
    LEGAL = "legal"                        # 法律文书
    PRESENTATION = "presentation"          # 演示文稿


class SubjectDomain(Enum):
    """学科领域枚举"""
    GENERAL = "general"
    PHYSICS = "physics"                    # 物理
    MATHEMATICS = "mathematics"            # 数学
    COMPUTER_SCIENCE = "computer_science" # 计算机科学
    ECONOMICS = "economics"                # 经济学
    LAW = "law"                            # 法律
    MEDICINE = "medicine"                  # 医学
    CHEMISTRY = "chemistry"               # 化学
    BIOLOGY = "biology"                    # 生物
    ENGINEERING = "engineering"            # 工程
    LITERATURE = "literature"              # 文学
    HISTORY = "history"                    # 历史
    PHILOSOPHY = "philosophy"              # 哲学


class WritingFormat(Enum):
    """写作格式枚举"""
    MARKDOWN = "markdown"
    LATEX = "latex"
    HTML = "html"
    DOCX = "docx"
    PLAIN = "plain"
    IEEE = "ieee"          # IEEE 论文格式
    APA = "apa"            # APA 论文格式
    CHICAGO = "chicago"   # 芝加哥格式
    MLA = "mla"            # MLA 格式


@dataclass
class IntentResult:
    """意图识别结果"""
    doc_type: DocType
    subject: SubjectDomain
    suggested_format: WritingFormat
    confidence: float                    # 0.0 - 1.0
    key_features: list[str] = field(default_factory=list)  # 识别出的关键特征
    detected_equations: list[str] = field(default_factory=list)  # 检测到的公式
    detected_citations: list[str] = field(default_factory=list)  # 检测到的引用
    language: str = "zh"                # 语言: zh / en
    suggested_skills: list[str] = field(default_factory=list)  # 建议加载的技能
    reasoning: str = ""                   # 识别推理过程


@dataclass
class AnalysisContext:
    """分析上下文"""
    file_path: Optional[Path] = None
    file_content: Optional[str] = None
    file_bytes: Optional[bytes] = None
    conversation_history: list[str] = field(default_factory=list)
    user_instructions: Optional[str] = None


class IntentDetector:
    """
    智能意图识别器

    能力：
    - 自动识别文档类型（论文/报告/小说等）
    - 判断学科领域（物理/经济/计算机等）
    - 检测公式、引用等专业元素
    - 生成置信度评估
    - 推荐写作格式和技能包
    """

    # 学科关键词映射
    SUBJECT_KEYWORDS = {
        SubjectDomain.PHYSICS: [
            "量子", "相对论", "电磁", "力学", "热力学", "光子", "电子", "核物理",
            "equation", "quantum", "relativity", "mechanics", "thermodynamics",
            "maxwell", "schrödinger", "lagrangian", "hamiltonian", "tensor"
        ],
        SubjectDomain.MATHEMATICS: [
            "定理", "证明", "微分", "积分", "拓扑", "代数", "几何", "概率",
            "theorem", "proof", "differential", "integral", "topology",
            "algebra", "geometry", "probability", "lemma", "corollary"
        ],
        SubjectDomain.COMPUTER_SCIENCE: [
            "算法", "数据结构", "机器学习", "深度学习", "神经网络", "代码",
            "algorithm", "machine learning", "neural network", "python",
            "software", "database", "api", "framework"
        ],
        SubjectDomain.ECONOMICS: [
            "GDP", "供需", "市场", "投资", "财务", "增长", "通胀",
            "supply demand", "market", "investment", "financial", "economy",
            "margin", "revenue", "profit", "equity"
        ],
        SubjectDomain.LAW: [
            "合同", "法条", "被告", "原告", "判决", "条款", "协议",
            "contract", "law", "plaintiff", "defendant", "verdict", "clause"
        ],
        SubjectDomain.MEDICINE: [
            "临床", "药物", "治疗", "诊断", "患者", "医学",
            "clinical", "drug", "therapy", "diagnosis", "patient", "symptom"
        ],
        SubjectDomain.LITERATURE: [
            "人物", "情节", "叙事", "主题", "象征", "隐喻", "小说",
            "character", "narrative", "theme", "metaphor", "novel", "plot"
        ],
    }

    # 文档类型模式
    DOC_TYPE_PATTERNS = {
        DocType.ACADEMIC_PAPER: [
            r"摘要", r"abstract", r"参考文献", r"references", r"第[一二三四五六七八九十]+章",
            r"\\section\{", r"\\cite\{", r"doi:", r"https://doi.org/",
            r"methodology?|experimental", r"introduction", r"conclusion"
        ],
        DocType.BUSINESS_REPORT: [
            r"季度报告", r"年度报告", r"财务分析", r"市场调研", r"swot",
            r"quarterly|annual report", r"financial analysis", r"market research"
        ],
        DocType.BUSINESS_PLAN: [
            r"商业计划书", r"bp", r"executive summary", r"商业模式", r"融资计划",
            r"商业模式画布", r"business model", r"investment", r"roi"
        ],
        DocType.NOVEL: [
            r"第[一二三四五六七八九十\d]+章", r"第[一二三四五六七八九十\d]+节",
            r"chapter\s+\d+", r"scene\s+\d+", r"人物.*?:", r"他.*?说道",
            r"她.*?想道", r"\"", r"\""
        ],
        DocType.TECHNICAL_DOC: [
            r"api", r"接口", r"文档", r"sdk", r"installation", r"usage",
            r"configuration", r"getting started", r"tutorial"
        ],
        DocType.LEGAL: [
            r"甲方", r"乙方", r"本协议", r"法律责任", r"违约", r"生效",
            r"party a", r"party b", r"agreement", r"liability", r"breach"
        ],
    }

    # 公式检测模式
    EQUATION_PATTERNS = [
        r"\$\$[^\$]+\$\$",           # $$...$$
        r"\$[^\$]+\$",               # $...$
        r"\\\[.*?\\\]",              # \[...\]
        r"\\begin\{equation\}",      # LaTeX equation 环境
        r"\\begin\{align\}",         # LaTeX align 环境
        r"\\nabla",                  # 梯度算子
        r"\\frac\{",                 # 分式
        r"\\int_",                   # 积分
        r"\\sum_",                   # 求和
        r"\^2|\^\{2\}",              # 平方
        r"\\partial",                # 偏导
    ]

    # 引用检测模式
    CITATION_PATTERNS = [
        r"\[\d+\]",                  # [1], [2,3]
        r"\([A-Z][a-z]+ et al\., \d{4}\)",  # (Smith et al., 2023)
        r"\([A-Z][a-z]+, \d{4}\)",   # (Smith, 2023)
        r"\\cite\{[^}]+\}",          # \cite{key}
        r"\\ref\{[^}]+\}",          # \ref{fig:1}
    ]

    def __init__(self):
        self._initialized = True

    def detect(self, context: AnalysisContext) -> IntentResult:
        """
        核心识别入口

        Args:
            context: 分析上下文

        Returns:
            IntentResult: 包含识别结果和置信度
        """
        results = []

        # 1. 基于文件内容的检测
        if context.file_content:
            content_results = self._analyze_content(context.file_content)
            results.extend(content_results)

        # 2. 基于文件类型的检测
        if context.file_path:
            file_type_result = self._analyze_file_type(context.file_path)
            if file_type_result:
                results.append(file_type_result)

        # 3. 基于对话历史的检测
        if context.conversation_history:
            chat_result = self._analyze_conversation(context.conversation_history)
            results.append(chat_result)

        # 4. 综合评分
        return self._aggregate_results(results, context)

    def detect_from_file(self, file_path: str | Path) -> IntentResult:
        """从文件路径快速检测"""
        path = Path(file_path)

        # 读取内容
        content = None
        try:
            if path.suffix.lower() in ['.md', '.txt', '.tex']:
                content = path.read_text(encoding='utf-8')
            elif path.suffix.lower() in ['.docx']:
                content = self._extract_docx_text(path)
            elif path.suffix.lower() in ['.pdf']:
                content = self._extract_pdf_text(path)
        except Exception:
            pass

        context = AnalysisContext(
            file_path=path,
            file_content=content,
        )
        return self.detect(context)

    def detect_from_bytes(self, data: bytes, mime_type: str) -> IntentResult:
        """从字节数据检测"""
        content = None

        # 尝试解码
        for encoding in ['utf-8', 'gbk', 'latin-1']:
            try:
                content = data.decode(encoding)
                break
            except Exception:
                continue

        context = AnalysisContext(
            file_bytes=data,
            file_content=content,
        )
        return self.detect(context)

    def _analyze_content(self, content: str) -> list[tuple[DocType, float, str]]:
        """分析文本内容"""
        results = []
        content_lower = content.lower()

        # 检测文档类型
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            score = 0
            matched = []
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    score += 1
                    matched.append(pattern)

            if score > 0:
                # 归一化
                confidence = min(score / len(patterns), 1.0)
                results.append((doc_type, confidence, f"内容匹配: {', '.join(matched[:3])}"))

        # 检测学科领域
        for subject, keywords in self.SUBJECT_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw.lower() in content_lower)
            if matches >= 2:
                confidence = min(matches / len(keywords) * 5, 1.0)
                results.append((subject, confidence, f"关键词命中: {matches}"))

        return results

    def _analyze_file_type(self, path: Path) -> Optional[tuple]:
        """基于文件扩展名判断"""
        suffix = path.suffix.lower()

        type_mapping = {
            '.tex': (DocType.ACADEMIC_PAPER, WritingFormat.LATEX, "LaTeX 文件"),
            '.docx': (DocType.ACADEMIC_PAPER, WritingFormat.DOCX, "Word 文档"),
            '.pdf': (DocType.ACADEMIC_PAPER, WritingFormat.PLAIN, "PDF 文档"),
            '.md': (DocType.BLOG, WritingFormat.MARKDOWN, "Markdown 文件"),
            '.txt': (DocType.GENERAL, WritingFormat.PLAIN, "纯文本"),
        }

        if suffix in type_mapping:
            doc_type, fmt, reason = type_mapping[suffix]
            return (doc_type, 0.7, reason)

        return None

    def _analyze_conversation(self, history: list[str]) -> tuple:
        """分析对话历史"""
        combined = " ".join(history).lower()

        # 关键词判断意图
        if any(kw in combined for kw in ["论文", "学术", "期刊", "paper", "journal"]):
            return (DocType.ACADEMIC_PAPER, 0.6, "对话关键词: 论文/学术")
        elif any(kw in combined for kw in ["商业计划", "融资", "bp", "pitch"]):
            return (DocType.BUSINESS_PLAN, 0.6, "对话关键词: 商业计划")
        elif any(kw in combined for kw in ["小说", "故事", "章节", "novel", "chapter"]):
            return (DocType.NOVEL, 0.6, "对话关键词: 小说/故事")

        return (DocType.GENERAL, 0.3, "对话历史不足")

    def _aggregate_results(self, results: list, context: AnalysisContext) -> IntentResult:
        """综合评分，生成最终结果"""
        if not results:
            return IntentResult(
                doc_type=DocType.GENERAL,
                subject=SubjectDomain.GENERAL,
                suggested_format=WritingFormat.MARKDOWN,
                confidence=0.1,
                reasoning="未检测到明确特征，使用默认设置"
            )

        # 找出最高分的文档类型
        doc_type_scores = {}
        subject_scores = {}
        reasoning_parts = []

        for result in results:
            if isinstance(result[0], DocType) and result[0] != SubjectDomain.GENERAL:
                if result[0] in doc_type_scores:
                    doc_type_scores[result[0]] = max(doc_type_scores[result[0]], result[1])
                else:
                    doc_type_scores[result[0]] = result[1]
                if len(result) > 2:
                    reasoning_parts.append(result[2])

        # 选择最高分
        best_doc_type = max(doc_type_scores.keys(), key=lambda x: doc_type_scores[x]) if doc_type_scores else DocType.GENERAL
        best_doc_conf = doc_type_scores.get(best_doc_type, 0.3)

        # 学科检测
        if context.file_content:
            content_lower = context.file_content.lower()
            for subject, keywords in self.SUBJECT_KEYWORDS.items():
                matches = sum(1 for kw in keywords if kw.lower() in content_lower)
                subject_scores[subject] = matches

        best_subject = max(subject_scores.keys(), key=lambda x: subject_scores[x]) if subject_scores else SubjectDomain.GENERAL

        # 检测公式
        equations = []
        if context.file_content:
            for pattern in self.EQUATION_PATTERNS:
                matches = re.findall(pattern, context.file_content)
                equations.extend(matches[:10])  # 最多10个

        # 检测引用
        citations = []
        if context.file_content:
            for pattern in self.CITATION_PATTERNS:
                matches = re.findall(pattern, context.file_content)
                citations.extend(matches[:10])

        # 判断语言
        lang = self._detect_language(context.file_content or "")

        # 推荐格式
        fmt = self._suggest_format(best_doc_type, best_subject)

        # 推荐技能
        skills = self._suggest_skills(best_doc_type, best_subject, bool(equations))

        return IntentResult(
            doc_type=best_doc_type,
            subject=best_subject,
            suggested_format=fmt,
            confidence=best_doc_conf,
            key_features=reasoning_parts,
            detected_equations=equations,
            detected_citations=citations,
            language=lang,
            suggested_skills=skills,
            reasoning="; ".join(reasoning_parts[:3]) if reasoning_parts else "基于内容分析"
        )

    def _detect_language(self, content: str) -> str:
        """检测语言"""
        # 简单基于字符集判断
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
        total_chars = len(content)

        if total_chars == 0:
            return "zh"

        chinese_ratio = chinese_chars / total_chars
        return "zh" if chinese_ratio > 0.3 else "en"

    def _suggest_format(self, doc_type: DocType, subject: SubjectDomain) -> WritingFormat:
        """推荐写作格式"""
        if doc_type == DocType.ACADEMIC_PAPER:
            if subject == SubjectDomain.PHYSICS or subject == SubjectDomain.MATHEMATICS:
                return WritingFormat.LATEX
            return WritingFormat.IEEE
        elif doc_type == DocType.BUSINESS_PLAN:
            return WritingFormat.MARKDOWN
        elif doc_type == DocType.NOVEL:
            return WritingFormat.MARKDOWN
        return WritingFormat.MARKDOWN

    def _suggest_skills(self, doc_type: DocType, subject: SubjectDomain, has_equations: bool) -> list[str]:
        """推荐加载的技能"""
        skills = ["general_writing"]

        if doc_type == DocType.ACADEMIC_PAPER:
            skills.append("academic_writing")
            skills.append("citation_manager")
            if has_equations:
                skills.append("latex_editor")
            if subject == SubjectDomain.PHYSICS:
                skills.append("physics_notation")
            elif subject == SubjectDomain.ECONOMICS:
                skills.append("financial_analysis")
        elif doc_type == DocType.BUSINESS_PLAN:
            skills.append("business_writing")
            skills.append("financial_analysis")
            skills.append("presentation")
        elif doc_type == DocType.NOVEL:
            skills.append("creative_writing")
            skills.append("character_management")

        return skills

    def _extract_docx_text(self, path: Path) -> Optional[str]:
        """提取 DOCX 文本"""
        try:
            from zipfile import ZipFile
            import xml.etree.ElementTree as ET

            with ZipFile(path) as z:
                with z.open('word/document.xml') as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                    texts = [t.text for t in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if t.text]
                    return ' '.join(texts)
        except Exception:
            return None

    def _extract_pdf_text(self, path: Path) -> Optional[str]:
        """提取 PDF 文本"""
        try:
            # 尝试使用 pdfminer 或 pypdf2
            # 这里简化为返回空，实际应该使用 pdfplumber 或 pdfminer
            return None
        except Exception:
            return None

    def get_confidence_label(self, confidence: float) -> str:
        """获取置信度标签"""
        if confidence >= 0.8:
            return "高置信"
        elif confidence >= 0.5:
            return "中置信"
        elif confidence >= 0.3:
            return "低置信"
        return "不确定"


# 单例
_detector: Optional[IntentDetector] = None


def get_intent_detector() -> IntentDetector:
    """获取意图检测器单例"""
    global _detector
    if _detector is None:
        _detector = IntentDetector()
    return _detector
