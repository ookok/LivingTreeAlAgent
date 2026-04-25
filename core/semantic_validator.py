"""
SemanticValidator - 语义一致性校验器
避免 AI "断章取义"的推理

核心能力：
- spaCy 依存句法解析
- 未闭合从句检测
- 本地 LLM 语义校验
- 不合格块重分块 + 摘要融合

问题场景：
- "因为天气冷，[块切在这里]" → 模型误判因果关系
- "他说如果明天不下雨，[块切在这里]" → 从句断裂
"""

import re
import json
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable, Iterator, TypedDict
from enum import Enum

from core.logger import get_logger

logger = get_logger('semantic_validator')

# 可选依赖
SPACY_AVAILABLE = False
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    pass


class ValidationResult(TypedDict):
    """校验结果"""
    is_valid: bool
    confidence: float
    issues: list[str]
    suggestion: str
    needs_rewrite: bool


class ChunkQuality(Enum):
    """分块质量"""
    EXCELLENT = "excellent"    # 完整、语义清晰
    GOOD = "good"              # 基本完整，轻微问题
    POOR = "poor"              # 需要重分块
    BROKEN = "broken"          # 严重断裂


@dataclass
class Chunk:
    """
    文本分块

    Attributes:
        text: 原始文本
        start: 起始位置
        end: 结束位置
        quality: 质量等级
        issues: 发现的问题列表
        is_standalone: 是否能独立回答问题
        dependency_tree: 依存句法树（可选）
    """
    text: str
    start: int
    end: int
    quality: ChunkQuality = ChunkQuality.GOOD
    issues: list[str] = field(default_factory=list)
    is_standalone: bool = True
    dependency_tree: Optional[dict] = None

    def get_length(self) -> int:
        return self.end - self.start

    def get_sentences(self) -> list[str]:
        """获取句子列表"""
        # 简单分句
        return re.split(r'[。！？\n]+', self.text)


class SemanticValidator:
    """
    语义一致性校验器

    使用 spaCy 解析依存句法树，检查：
    1. 主谓宾完整性
    2. 从句闭合性（CC 连词后的主句）
    3. 引用完整性（引号、成对符号）
    4. 语义独立性

    使用示例：
        validator = SemanticValidator()

        # 校验单个块
        result = validator.validate_chunk(
            "因为天气冷，所以",
            prev_chunk="我喜欢喝热咖啡",
            next_chunk="我决定买一件羽绒服"
        )
        # -> is_valid=False, issues=["从句未闭合"]

        # 重分块
        new_chunks = validator.rechunk(
            "因为天气冷，所以我决定买一件羽绒服",
            max_length=50
        )
    """

    # 未闭合模式
    UNCLOSED_PATTERNS = [
        (r'因为(.+?)，$', "因为...所以 结构未闭合"),
        (r'如果(.+?)，$', "条件从句未闭合"),
        (r'虽然(.+?)，$', "让步从句未闭合"),
        (r'当(.+?)，$', "时间从句未闭合"),
        (r'在(.+?)中，$', "介词短语未闭合"),
        (r'为了(.+?)，$', "目的从句未闭合"),
    ]

    # 需要成对匹配的符号
    PAIRED_CHARS = {
        '「': '」', '"': '"', "'": "'",
        '(': ')', '【': '】', '（': '）',
        '[': ']', '{': '}',
    }

    def __init__(
        self,
        spacy_model: str = "zh_core_web_sm",
        llm_judge: Optional[Callable] = None,
        min_standalone_length: int = 20,
    ):
        """
        Args:
            spacy_model: spaCy 模型名称
            llm_judge: LLM 判断器（可选，用于深度语义分析）
            min_standalone_length: 最小独立文本长度
        """
        self.spacy_model = spacy_model
        self.llm_judge = llm_judge
        self.min_standalone_length = min_standalone_length

        # spaCy 模型
        self._nlp = None
        if SPACY_AVAILABLE:
            self._init_spacy()

        # 统计
        self._stats = {
            "total_chunks": 0,
            "valid_chunks": 0,
            "rewritten_chunks": 0,
            "issues_found": {
                "unclosed": 0,
                "orphan": 0,
                "paired": 0,
                "semantic": 0,
            }
        }

    def _init_spacy(self):
        """初始化 spaCy 模型"""
        try:
            self._nlp = spacy.load(self.spacy_model)
            logger.info(f"✓ 加载 spaCy 模型: {self.spacy_model}")
        except Exception as e:
            logger.info(f"⚠️ 加载 spaCy 模型失败: {e}")
            self._nlp = None

    def validate_chunk(
        self,
        chunk_text: str,
        prev_text: str = "",
        next_text: str = "",
    ) -> ValidationResult:
        """
        校验单个文本块

        Args:
            chunk_text: 待校验文本
            prev_text: 前一个块文本
            next_text: 后一个块文本

        Returns:
            校验结果
        """
        self._stats["total_chunks"] += 1

        issues = []
        quality = ChunkQuality.GOOD
        needs_rewrite = False

        # 1. 检查未闭合从句
        unclosed = self._check_unclosed_clause(chunk_text)
        if unclosed:
            issues.append(unclosed)
            quality = ChunkQuality.POOR
            needs_rewrite = True
            self._stats["issues_found"]["unclosed"] += 1

        # 2. 检查孤立的连词
        orphan = self._check_orphan_conjunctions(chunk_text, prev_text)
        if orphan:
            issues.append(orphan)
            quality = ChunkQuality.POOR
            self._stats["issues_found"]["orphan"] += 1

        # 3. 检查成对符号匹配
        paired = self._check_paired_chars(chunk_text)
        if paired:
            issues.append(paired)
            quality = ChunkQuality.POOR
            needs_rewrite = True
            self._stats["issues_found"]["paired"] += 1

        # 4. spaCy 句法分析（如果有模型）
        if self._nlp:
            spacy_issues = self._spacy_analysis(chunk_text)
            if spacy_issues:
                issues.extend(spacy_issues)
                self._stats["issues_found"]["semantic"] += 1

        # 5. LLM 深度判断（如果有）
        confidence = 0.6
        if self.llm_judge and chunk_text:
            try:
                llm_result = self.llm_judge(chunk_text)
                if llm_result.get("is_valid", True) is False:
                    issues.append(f"LLM 判断: {llm_result.get('reason', '语义不独立')}")
                    quality = ChunkQuality.POOR
                    needs_rewrite = True
                confidence = llm_result.get("confidence", 0.8)
            except Exception:
                pass
        else:
            # 基于规则的置信度
            if quality == ChunkQuality.POOR:
                confidence = 0.4
            elif not issues:
                confidence = 0.7

        # 判断是否有效
        is_valid = quality in (ChunkQuality.EXCELLENT, ChunkQuality.GOOD) and not needs_rewrite

        if is_valid:
            self._stats["valid_chunks"] += 1

        # 生成建议
        suggestion = self._generate_suggestion(chunk_text, issues)

        return ValidationResult(
            is_valid=is_valid,
            confidence=confidence,
            issues=issues,
            suggestion=suggestion,
            needs_rewrite=needs_rewrite,
        )

    def _check_unclosed_clause(self, text: str) -> Optional[str]:
        """检查未闭合从句"""
        for pattern, desc in self.UNCLOSED_PATTERNS:
            if re.search(pattern, text):
                return desc
        return None

    def _check_orphan_conjunctions(self, text: str, prev_text: str) -> Optional[str]:
        """
        检查孤立的连词

        检查 CC（ coordinating conjunction）后面是否有主句
        常见连词：但是、然而、不过、而
        """
        orphan_patterns = [
            r'但是[，。]',
            r'然而[，。]',
            r'不过[，。]',
            r'而[，。]',
            r'同时[，。]',
        ]

        for pattern in orphan_patterns:
            matches = re.findall(pattern, text)
            if matches:
                # 检查是否只有连词本身（没有后续内容）
                cleaned = re.sub(pattern, '', text).strip()
                if not cleaned or len(cleaned) < 5:
                    return f"连词后缺少主句"

        return None

    def _check_paired_chars(self, text: str) -> Optional[str]:
        """检查成对符号匹配"""
        stack = []

        for char in text:
            if char in self.PAIRED_CHARS:
                stack.append(char)
            elif char in self.PAIRED_CHARS.values():
                # 查找对应的开符号
                open_char = None
                for open_c, close_c in self.PAIRED_CHARS.items():
                    if close_c == char:
                        open_char = open_c
                        break

                if open_char and stack and stack[-1] == open_char:
                    stack.pop()
                elif open_char:
                    return f"不成对的闭合符号: {char}"

        if stack:
            return f"未闭合的符号: {', '.join(stack)}"

        return None

    def _spacy_analysis(self, text: str) -> list[str]:
        """使用 spaCy 进行句法分析"""
        if not self._nlp or not text:
            return []

        issues = []
        doc = self._nlp(text)

        # 检查句子边界
        sentences = list(doc.sents)
        if len(sentences) > 1:
            # 检查是否有从句开头
            for sent in sentences[1:]:  # 跳过第一句
                first_token = sent[0]
                # 如果第二句以连词开头，可能是断句问题
                if first_token.pos_ == "CCONJ" or first_token.pos_ == "ADP":
                    issues.append(f"可能断句不当: 第二句以 '{first_token.text}' 开头")

        # 检查依存关系
        for token in doc:
            # 如果有 root 依存关系异常
            if token.dep_ == "ROOT" and token.pos_ not in ("VERB", "ADJ", "NOUN"):
                issues.append(f"ROOT 依存异常: '{token.text}' (pos={token.pos_})")

        return issues

    def _generate_suggestion(self, text: str, issues: list[str]) -> str:
        """生成修复建议"""
        if not issues:
            return "文本质量良好，无需修改"

        suggestions = []

        for issue in issues:
            if "未闭合" in issue or "从句" in issue:
                suggestions.append("将本块与下一块合并，确保从句完整")
            elif "连词" in issue:
                suggestions.append("检查连词前后是否完整，考虑合并相邻块")
            elif "符号" in issue:
                suggestions.append("检查成对符号是否匹配")
            elif "断句" in issue:
                suggestions.append("重新分句，避免在从句中途断句")

        return " | ".join(suggestions) if suggestions else "建议人工检查"

    def rechunk(
        self,
        text: str,
        prev_text: str = "",
        next_text: str = "",
        max_length: int = 500,
        overlap: int = 50,
    ) -> list[Chunk]:
        """
        重分块（融合摘要）

        当原始分块不合格时，将前后块合并重新分块

        Args:
            text: 当前块文本
            prev_text: 前一个块文本
            next_text: 后一个块文本
            max_length: 最大块长度
            overlap: 重叠长度

        Returns:
            新的分块列表
        """
        self._stats["rewritten_chunks"] += 1

        # 合并上下文
        full_context = prev_text + text + next_text

        if len(full_context) <= max_length:
            # 文本较短，直接返回完整块
            return [Chunk(
                text=full_context,
                start=0,
                end=len(full_context),
                quality=ChunkQuality.GOOD,
            )]

        # 分句
        sentences = self._split_sentences(full_context)

        # 重新分组（确保句子完整性）
        chunks = []
        current_chunk = ""
        current_start = 0

        for i, sent in enumerate(sentences):
            sent_with_punct = sent + ("。" if sent and sent[-1] not in "。！？" else "")

            if len(current_chunk) + len(sent_with_punct) <= max_length:
                current_chunk += sent_with_punct
            else:
                # 保存当前块
                if current_chunk:
                    chunks.append(Chunk(
                        text=current_chunk,
                        start=current_start,
                        end=current_start + len(current_chunk),
                    ))
                    current_start += len(current_chunk) - overlap
                    if current_start < 0:
                        current_start = 0

                # 开始新块（带重叠）
                current_chunk = prev_text[-overlap:] + sent_with_punct if prev_text else sent_with_punct

        # 保存最后一块
        if current_chunk:
            chunks.append(Chunk(
                text=current_chunk,
                start=current_start,
                end=current_start + len(current_chunk),
            ))

        # 校验每个新块
        validated_chunks = []
        for i, chunk in enumerate(chunks):
            prev = chunks[i - 1].text if i > 0 else prev_text
            nxt = chunks[i + 1].text if i < len(chunks) - 1 else next_text

            result = self.validate_chunk(chunk.text, prev, nxt)
            chunk.quality = ChunkQuality.EXCELLENT if result["is_valid"] else ChunkQuality.GOOD
            chunk.issues = result["issues"]
            chunk.is_standalone = result["is_valid"]
            validated_chunks.append(chunk)

        return validated_chunks

    def _split_sentences(self, text: str) -> list[str]:
        """分句"""
        # 使用简单的正则分句
        sentences = re.split(r'([。！？\n]+)', text)
        result = []

        # 合并句子和标点
        for i in range(0, len(sentences) - 1, 2):
            sent = sentences[i]
            punct = sentences[i + 1] if i + 1 < len(sentences) else ""
            if sent.strip():
                result.append(sent + punct)

        return result

    def validate_chunks(
        self,
        chunks: list[Chunk],
    ) -> Iterator[tuple[int, ValidationResult]]:
        """
        批量校验分块

        Yields:
            (chunk_index, result) 元组
        """
        for i, chunk in enumerate(chunks):
            prev_text = chunks[i - 1].text if i > 0 else ""
            next_text = chunks[i + 1].text if i < len(chunks) - 1 else ""

            result = self.validate_chunk(chunk.text, prev_text, next_text)
            yield i, result

    def can_standalone_answer(self, chunk_text: str, question: str) -> dict:
        """
        判断块是否能独立回答问题

        Args:
            chunk_text: 文本块
            question: 问题

        Returns:
            判断结果
        """
        # 长度检查
        if len(chunk_text) < self.min_standalone_length:
            return {
                "can_answer": False,
                "reason": f"文本太短 ({len(chunk_text)} < {self.min_standalone_length})",
                "confidence": 0.9,
            }

        # 语义覆盖检查
        if self.llm_judge:
            try:
                prompt = f"""判断以下文本块是否能独立回答问题。

问题：{question}

文本块：{chunk_text[:500]}

请判断并返回 JSON：
{{"can_answer": true/false, "reason": "原因", "confidence": 0.0-1.0}}
"""
                result = self.llm_judge(prompt)
                return result
            except Exception:
                pass

        # 回退：关键词匹配
        question_keywords = set(question.lower().split())
        chunk_keywords = set(chunk_text.lower().split())
        overlap = len(question_keywords & chunk_keywords) / len(question_keywords) if question_keywords else 0

        return {
            "can_answer": overlap > 0.3,
            "reason": f"关键词覆盖率: {overlap:.0%}",
            "confidence": 0.5,
        }

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = self._stats.copy()
        if stats["total_chunks"] > 0:
            stats["valid_rate"] = stats["valid_chunks"] / stats["total_chunks"]
        else:
            stats["valid_rate"] = 0.0
        return stats


# ── Chonkie 集成（可选）────────────────────────────────────────────

class ChonkieValidator:
    """
    Chonkie 分块验证器

    封装 Chonkie 的智能分块，并验证每个块的质量
    """

    def __init__(self, validator: SemanticValidator):
        self.validator = validator
        self._chunker = None

        # 尝试导入 Chonkie
        try:
            from chonkie import RecursiveChunker
            self._chunker = RecursiveChunker()
        except ImportError:
            logger.info("⚠️ chonkie 未安装，使用简单分块")

    def chunk_with_validation(
        self,
        text: str,
        max_length: int = 500,
    ) -> list[Chunk]:
        """
        分块并验证

        Returns:
            通过验证的分块列表
        """
        if self._chunker:
            # 使用 Chonkie 分块
            raw_chunks = self._chunker.chunk(text)
            chunks = [
                Chunk(
                    text=c.text,
                    start=c.start_index,
                    end=c.end_index,
                )
                for c in raw_chunks
            ]
        else:
            # 使用内置分块
            chunks = self.validator.rechunk(text, max_length=max_length)

        # 验证并修复
        validated = []
        for chunk in chunks:
            result = self.validator.validate_chunk(chunk.text)
            if result["needs_rewrite"]:
                # 重分块
                fixed = self.validator.rechunk(
                    chunk.text,
                    max_length=max_length,
                )
                validated.extend(fixed)
            else:
                validated.append(chunk)

        return validated
