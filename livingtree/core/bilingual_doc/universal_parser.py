"""
通用文档解析器 (Universal Document Parser)
遵循自我进化原则：从文档中学习型结构模式，而非预置各类型解析器

架构指南参考: docs/LIVINGTREE_ARCHITECTURE_GUIDE.md (章节 5.3.5)

核心借鉴: markitdown (匹配度75%)
- 通用解析器 + 自适应学习
- 检测文档类型
- 学习结构模式
- 应用学习的模式解析
"""
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging
from enum import Enum

from business.global_model_router import GlobalModelRouter, ModelCapability


logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """文档类型 - 从学习中扩展"""
    UNKNOWN = "unknown"
    REPORT = "report"
    ESSAY = "essay"
    TECHNICAL = "technical"
    EMAIL = "email"
    LETTER = "letter"
    ARTICLE = "article"
    # 可以从学习中自动添加新的类型


@dataclass
class DocumentStructure:
    """文档结构 - 从学习中识别"""
    doc_type: DocumentType
    sections: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    patterns: List[str] = field(default_factory=list)  # 识别的模式


@dataclass
class ParsedResult:
    """解析结果"""
    raw_text: str
    structure: DocumentStructure
    parsed_content: Dict[str, Any]
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class UniversalParser:
    """
    通用文档解析器

    核心原则：
    ❌ 不预置各文档类型的解析器
    ✅ 使用通用解析器 + 自适应学习
    ✅ 检测文档类型
    ✅ 学习结构模式
    ✅ 应用学习的模式解析新文档
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.router = GlobalModelRouter()
        self.storage_path = storage_path or Path.home() / ".livingtree" / "parser_patterns.json"
        self.learned_patterns: Dict[str, Dict[str, Any]] = {}  # doc_type -> patterns
        self.doc_type_examples: Dict[str, List[str]] = {}  # doc_type -> [example_texts]
        self.parse_history: List[Dict[str, Any]] = []
        self._load_patterns()

    def _load_patterns(self):
        """加载已学习的解析模式"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.learned_patterns = data.get("patterns", {})
                    self.doc_type_examples = data.get("examples", {})
                    self.parse_history = data.get("history", [])
                logger.info(f"✅ 已加载 {len(self.learned_patterns)} 个文档类型的解析模式")
            except Exception as e:
                logger.warning(f"⚠️ 加载解析模式失败: {e}")

    def _save_patterns(self):
        """保存学习的解析模式"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "patterns": self.learned_patterns,
                "examples": self.doc_type_examples,
                "history": self.parse_history[-200:]  # 只保留最近200条
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存解析模式失败: {e}")

    async def parse(self, doc: 'Document') -> ParsedResult:
        """
        通用文档解析入口

        流程：
        1. 检测文档类型
        2. 获取/学习结构模式
        3. 应用模式解析
        4. 返回结构化结果
        """
        logger.info(f"📄 开始解析文档: {getattr(doc, 'name', 'unknown')}")

        # 1. 检测文档类型
        doc_type = await self._detect_type(doc)

        # 2. 获取/学习结构模式
        patterns = await self._get_or_learn_patterns(doc, doc_type)

        # 3. 应用模式解析
        structure = await self._apply_patterns(doc, doc_type, patterns)

        # 4. 解析内容
        parsed_content = await self._parse_content(doc, structure)

        # 5. 记录历史
        self.parse_history.append({
            "timestamp": self._get_timestamp(),
            "doc_type": doc_type.value,
            "confidence": structure.confidence,
            "success": True
        })
        self._save_patterns()

        return ParsedResult(
            raw_text=getattr(doc, 'text', str(doc)),
            structure=structure,
            parsed_content=parsed_content,
            confidence=structure.confidence
        )

    async def _detect_type(self, doc: 'Document') -> DocumentType:
        """
        检测文档类型

        学习型实现：
        - 先尝试匹配已学习的类型
        - 如果不匹配，使用 LLM 识别
        - 记录新类型
        """
        text = getattr(doc, 'text', str(doc))

        # 1. 尝试匹配已学习的类型
        matched_type = self._match_learned_type(text)
        if matched_type:
            logger.info(f"🎯 匹配到已学习类型: {matched_type}")
            return matched_type

        # 2. 使用 LLM 识别
        doc_type = await self._detect_type_with_llm(text)

        # 3. 学习新类型
        if doc_type != DocumentType.UNKNOWN:
            await self._learn_doc_type(doc_type, text)
            self._save_patterns()

        return doc_type

    def _match_learned_type(self, text: str) -> Optional[DocumentType]:
        """匹配已学习的文档类型"""
        for doc_type_str, patterns in self.learned_patterns.items():
            keywords = patterns.get("keywords", [])
            if any(kw in text for kw in keywords):
                try:
                    return DocumentType(doc_type_str)
                except ValueError:
                    continue
        return None

    async def _detect_type_with_llm(self, text: str) -> DocumentType:
        """使用 LLM 检测文档类型"""
        prompt = f"""
作为一个文档类型识别专家，分析以下文档，识别其类型。

文档内容（前500字）:
{text[:500]}

要求：
1. 判断文档类型（从以下选择或创建新的）：
   - report: 报告类（环评报告、研究报告等）
   - essay: 论文/文章
   - technical: 技术文档
   - email: 邮件
   - letter: 信函
   - article: 新闻/博客
   - 或其他你认为合适的类型
2. 返回 JSON 格式

返回格式:
{{
    "doc_type": "类型",
    "confidence": 0.9,
    "keywords": ["关键词1", "关键词2", ...],
    "reason": "判断理由"
}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.1
            )
            result = json.loads(response)

            doc_type_str = result.get("doc_type", "unknown")
            try:
                return DocumentType(doc_type_str)
            except ValueError:
                # 新类型，动态创建
                return DocumentType.UNKNOWN

        except Exception as e:
            logger.error(f"❌ LLM 文档类型识别失败: {e}")
            return DocumentType.UNKNOWN

    async def _learn_doc_type(self, doc_type: DocumentType, text: str):
        """学习新的文档类型"""
        doc_type_str = doc_type.value

        # 使用 LLM 提取特征
        prompt = f"""
作为一个文档分析专家，分析以下文档，提取结构模式。

文档类型: {doc_type_str}
文档内容（前1000字）:
{text[:1000]}

要求：
1. 识别文档的结构模式（如：标题→摘要→正文→结论）
2. 提取关键词
3. 返回 JSON 格式

返回格式:
{{
    "keywords": ["关键词1", "关键词2", ...],
    "structure_patterns": ["模式1", "模式2", ...],
    "section_patterns": [
        {{"name": "标题", "patterns": ["# ", "标题:", ...]}},
        ...
    ]
}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.2
            )
            result = json.loads(response)

            # 保存学习的模式
            self.learned_patterns[doc_type_str] = {
                "keywords": result.get("keywords", []),
                "structure_patterns": result.get("structure_patterns", []),
                "section_patterns": result.get("section_patterns", []),
                "learned_at": self._get_timestamp(),
                "usage_count": 1
            }

            # 保存示例
            if doc_type_str not in self.doc_type_examples:
                self.doc_type_examples[doc_type_str] = []
            self.doc_type_examples[doc_type_str].append(text[:500])  # 保存前500字

            logger.info(f"📝 学习新文档类型: {doc_type_str}")

        except Exception as e:
            logger.error(f"❌ 学习文档类型失败: {e}")

    async def _get_or_learn_patterns(self, doc: 'Document', doc_type: DocumentType) -> Dict[str, Any]:
        """
        获取或学习结构模式

        如果已学习过，返回学习的模式
        如果未学习，学习新模式
        """
        doc_type_str = doc_type.value

        if doc_type_str in self.learned_patterns:
            patterns = self.learned_patterns[doc_type_str]
            # 更新使用次数
            patterns["usage_count"] = patterns.get("usage_count", 0) + 1
            logger.info(f"🧠 使用已学习模式: {doc_type_str} (使用次数: {patterns['usage_count']})")
            return patterns

        # 未学习，学习新模式
        text = getattr(doc, 'text', str(doc))
        await self._learn_doc_type(doc_type, text)
        return self.learned_patterns.get(doc_type_str, {})

    async def _apply_patterns(self, doc: 'Document', doc_type: DocumentType, patterns: Dict[str, Any]) -> DocumentStructure:
        """应用学习的模式解析文档结构"""
        text = getattr(doc, 'text', str(doc))

        prompt = f"""
作为一个文档结构解析专家，使用以下学习的模式解析文档。

文档类型: {doc_type.value}
学习的模式:
{json.dumps(patterns, ensure_ascii=False, indent=2)}

文档内容（前2000字）:
{text[:2000]}

要求：
1. 识别文档的章节结构
2. 提取元数据（标题、作者、日期等）
3. 返回 JSON 格式

返回格式:
{{
    "sections": [
        {{"name": "标题", "content": "...", "level": 1}},
        {{"name": "摘要", "content": "...", "level": 2}},
        ...
    ],
    "metadata": {{
        "title": "标题",
        "author": "作者",
        "date": "日期"
    }},
    "confidence": 0.9
}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.1
            )
            result = json.loads(response)

            return DocumentStructure(
                doc_type=doc_type,
                sections=result.get("sections", []),
                metadata=result.get("metadata", {}),
                patterns=patterns.get("structure_patterns", []),
                confidence=result.get("confidence", 0.5)
            )

        except Exception as e:
            logger.error(f"❌ 应用模式解析失败: {e}")
            # 兜底：简单分段
            return DocumentStructure(
                doc_type=doc_type,
                sections=[{"name": "全文", "content": text, "level": 1}],
                confidence=0.3
            )

    async def _parse_content(self, doc: 'Document', structure: DocumentStructure) -> Dict[str, Any]:
        """解析文档内容"""
        # 根据结构提取内容
        content = {
            "sections": structure.sections,
            "metadata": structure.metadata,
            "doc_type": structure.doc_type.value,
            "parsed_at": self._get_timestamp()
        }

        # 可以扩展：提取表格、图片、公式等
        return content

    async def learn_from_feedback(self, feedback: Dict[str, Any]):
        """
        从反馈中学习，优化解析

        反馈格式:
        {
            "doc_type": "report",
            "parsed_result": {...},
            "user_corrections": [...],  # 用户修正
            "rating": 0.8  # 解析质量评分 0-1
        }
        """
        doc_type = feedback.get("doc_type", "unknown")
        rating = feedback.get("rating", 0.5)

        if doc_type in self.learned_patterns:
            patterns = self.learned_patterns[doc_type]

            # 根据评分调整
            if rating < 0.6:
                # 低评分，重新学习
                logger.info(f"🔄 重新学习解析模式: {doc_type} (评分: {rating})")
                text = feedback.get("text", "")
                if text:
                    await self._learn_doc_type(DocumentType(doc_type), text)
            else:
                # 高评分，保留并更新
                patterns["usage_count"] = patterns.get("usage_count", 0) + 1

        # 记录反馈
        self.parse_history.append({
            "timestamp": self._get_timestamp(),
            "doc_type": doc_type,
            "rating": rating,
            "has_corrections": bool(feedback.get("user_corrections"))
        })

        self._save_patterns()
        logger.info(f"📈 已从反馈中学习: {doc_type}")

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    def get_stats(self) -> Dict[str, Any]:
        """获取解析统计信息"""
        if not self.learned_patterns:
            return {"total_doc_types": 0}

        total_parses = sum(p.get("usage_count", 0) for p in self.learned_patterns.values())

        return {
            "total_doc_types": len(self.learned_patterns),
            "total_parses": total_parses,
            "total_examples": sum(len(examples) for examples in self.doc_type_examples.values()),
            "doc_types": [
                {
                    "type": doc_type,
                    "usage_count": self.learned_patterns[doc_type].get("usage_count", 0),
                    "keywords": self.learned_patterns[doc_type].get("keywords", [])[:3]
                }
                for doc_type in sorted(self.learned_patterns.keys(),
                                        key=lambda x: -self.learned_patterns[x].get("usage_count", 0))
            ]
        }
