# -*- coding: utf-8 -*-
"""
分块分析器 - Chunk Analyzer
===========================

对分块后的内容进行深度分析，提取关键信息和关系。

核心能力：
1. 内容类型识别
2. 关键信息提取
3. 关系分析
4. 质量评估

Author: Hermes Desktop Team
Date: 2026-04-24
from __future__ import annotations
"""


import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)

from .semantic_chunker import Chunk, ChunkType
from .adaptive_compressor import SegmentType


class AnalysisDepth(Enum):
    """分析深度"""
    QUICK = "quick"         # 快速分析（关键词+类型）
    STANDARD = "standard"   # 标准分析（结构+关系）
    DEEP = "deep"          # 深度分析（语义+推理）


class EntityType(Enum):
    """实体类型"""
    PERSON = "person"       # 人名
    ORGANIZATION = "org"    # 组织
    LOCATION = "location"  # 地点
    CONCEPT = "concept"    # 概念
    PRODUCT = "product"    # 产品
    TECHNOLOGY = "tech"     # 技术
    EVENT = "event"        # 事件
    NUMBER = "number"      # 数字
    DATE = "date"          # 日期


@dataclass
class Entity:
    """实体"""
    text: str
    entity_type: EntityType
    start: int
    end: int
    confidence: float = 1.0
    
    def __repr__(self):
        return f"Entity({self.entity_type.value}: {self.text[:20]}...)"


@dataclass
class Relation:
    """关系"""
    source: str
    target: str
    relation_type: str
    confidence: float = 1.0
    
    def __repr__(self):
        return f"Relation({self.source[:10]} -> {self.target[:10]})"


@dataclass
class ChunkAnalysis:
    """
    分块分析结果
    
    Attributes:
        chunk_id: 分块索引
        content_type: 内容类型
        entities: 实体列表
        relations: 关系列表
        key_points: 关键点
        summary: 摘要
        questions: 可追问的问题
        complexity: 复杂度 0-1
        quality: 质量评分 0-1
        metadata: 元数据
    """
    chunk_id: int
    content_type: SegmentType
    entities: List[Entity] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)
    summary: str = ""
    questions: List[str] = field(default_factory=list)
    complexity: float = 0.5
    quality: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def entity_count(self) -> int:
        return len(self.entities)
    
    @property
    def relation_count(self) -> int:
        return len(self.relations)


@dataclass
class AnalysisResult:
    """
    完整分析结果
    
    Attributes:
        chunk_analyses: 每个分块的分析
        cross_chunk_relations: 跨分块关系
        global_entities: 全局实体
        global_relations: 全局关系
        overall_summary: 整体摘要
        key_themes: 主题列表
        insights: 洞察
        recommended_questions: 推荐追问
    """
    chunk_analyses: List[ChunkAnalysis] = field(default_factory=list)
    cross_chunk_relations: List[Relation] = field(default_factory=list)
    global_entities: List[Entity] = field(default_factory=list)
    global_relations: List[Relation] = field(default_factory=list)
    overall_summary: str = ""
    key_themes: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    recommended_questions: List[str] = field(default_factory=list)
    
    @property
    def total_entities(self) -> int:
        return len(self.global_entities)
    
    @property
    def total_relations(self) -> int:
        return len(self.global_relations)
    
    @property
    def coverage(self) -> float:
        """分析覆盖率"""
        if not self.chunk_analyses:
            return 0.0
        return len([a for a in self.chunk_analyses if a.quality > 0.5]) / len(self.chunk_analyses)


class ChunkAnalyzer:
    """
    分块分析器
    
    对分块后的内容进行多维度分析。
    """
    
    def __init__(
        self,
        depth: AnalysisDepth = AnalysisDepth.STANDARD,
        enable_ner: bool = True,
        enable_relation: bool = True,
    ):
        """
        初始化分析器
        
        Args:
            depth: 分析深度
            enable_ner: 是否启用命名实体识别
            enable_relation: 是否启用关系分析
        """
        self.depth = depth
        self.enable_ner = enable_ner
        self.enable_relation = enable_relation
        
        # 编译正则
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则表达式"""
        # 数字模式
        self.number_pattern = re.compile(
            r'\d+\.?\d*\s*[%℃万元亿元个点次天年月]?\b'
        )
        
        # 日期模式
        self.date_pattern = re.compile(
            r'\d{4}年\d{1,2}月\d{0,2}日?|'
            r'\d{4}-\d{2}-\d{2}|'
            r'\d{4}/\d{2}/\d{2}'
        )
        
        # 百分比模式
        self.percent_pattern = re.compile(r'\d+\.?\d*%')
        
        # 实体模式
        self.person_pattern = re.compile(
            r'[A-Z\u4e00-\u9fa5][a-z\u4e00-\u9fa5]{1,3}\s*(先生|女士|博士|教授|经理|总监)?|'
            r'张\d{3,4}'
        )
        
        # 组织模式
        self.org_pattern = re.compile(
            r'(公司|集团|医院|学校|银行|医院|研究所|实验室|机构|部门)\s*'
        )
        
        # 地点模式
        self.location_pattern = re.compile(
            r'(北京|上海|深圳|广州|杭州|成都|武汉|西安|南京)\s*(分部|分公司|办公室)?'
        )
        
        # 技术术语模式
        self.tech_pattern = re.compile(
            r'(AI|ML|LLM|RAG|KB|API|SDK|ORM|API)\b|'
            r'\w+(算法|模型|框架|系统|平台|引擎)'
        )
        
        # 代码模式
        self.code_pattern = re.compile(r'```[\s\S]*?```|`[^`]+`')
        
        # 引用模式
        self.quote_pattern = re.compile(r'[""''""''](.+?)[""''""'']')
        
        # 关键断言模式
        self.assertion_patterns = [
            (re.compile(r'是|指|代表|表示'), "定义"),
            (re.compile(r'因为|由于|所以|因此'), "因果"),
            (re.compile(r'但是|然而|不过|可是'), "转折"),
            (re.compile(r'如果|当|当...时'), "条件"),
            (re.compile(r'首先|其次|最后|第一|第二|第三'), "顺序"),
            (re.compile(r'重要|关键|核心|必须|应该'), "强调"),
        ]
    
    def analyze_chunk(self, chunk: Chunk) -> ChunkAnalysis:
        """
        分析单个分块
        
        Args:
            chunk: 分块
        
        Returns:
            ChunkAnalysis: 分析结果
        """
        content = chunk.content
        
        # 内容类型识别
        content_type = self._classify_content(content)
        
        # 实体识别
        entities = []
        if self.enable_ner:
            entities = self._extract_entities(content)
        
        # 关系分析
        relations = []
        if self.enable_relation:
            relations = self._extract_relations(content, entities)
        
        # 关键点提取
        key_points = self._extract_key_points(content)
        
        # 摘要生成
        summary = self._summarize(content)
        
        # 追问生成
        questions = self._generate_questions(chunk, content_type)
        
        # 复杂度评估
        complexity = self._assess_complexity(content)
        
        # 质量评估
        quality = self._assess_quality(content, content_type)
        
        return ChunkAnalysis(
            chunk_id=chunk.index,
            content_type=content_type,
            entities=entities,
            relations=relations,
            key_points=key_points,
            summary=summary,
            questions=questions,
            complexity=complexity,
            quality=quality,
            metadata={
                "chunk_type": chunk.chunk_type.value,
                "length": chunk.length,
                "keywords": chunk.keywords,
            }
        )
    
    def analyze_chunks(self, chunks: List[Chunk]) -> AnalysisResult:
        """
        分析多个分块
        
        Args:
            chunks: 分块列表
        
        Returns:
            AnalysisResult: 完整分析结果
        """
        # 分析每个分块
        chunk_analyses = [self.analyze_chunk(c) for c in chunks]
        
        # 跨分块关系
        cross_relations = self._analyze_cross_chunk_relations(chunks, chunk_analyses)
        
        # 全局实体和关系
        global_entities = self._merge_global_entities(chunk_analyses)
        global_relations = self._merge_global_relations(chunk_analyses, cross_relations)
        
        # 整体摘要
        overall_summary = self._generate_overall_summary(chunk_analyses)
        
        # 主题提取
        key_themes = self._extract_themes(chunk_analyses)
        
        # 洞察生成
        insights = self._generate_insights(chunk_analyses, key_themes)
        
        # 推荐追问
        recommended_questions = self._generate_recommended_questions(chunk_analyses)
        
        return AnalysisResult(
            chunk_analyses=chunk_analyses,
            cross_chunk_relations=cross_relations,
            global_entities=global_entities,
            global_relations=global_relations,
            overall_summary=overall_summary,
            key_themes=key_themes,
            insights=insights,
            recommended_questions=recommended_questions,
        )
    
    def _classify_content(self, content: str) -> SegmentType:
        """分类内容类型"""
        from .adaptive_compressor import SegmentType
        
        # 检查代码
        if self.code_pattern.search(content):
            return SegmentType.CODE
        
        # 检查数据
        if self.number_pattern.search(content) and self.percent_pattern.search(content):
            return SegmentType.DATA
        
        # 检查定义
        if any(p.match(content[:50]) for p, _ in self.assertion_patterns[:1] if '定义' in _):
            return SegmentType.DEFINITION
        
        # 检查结论
        if any(p.match(content[:30]) for p, _ in self.assertion_patterns[:2] if '因果' in _ or '因此' in _):
            return SegmentType.CONCLUSION
        
        # 检查例子
        if '例如' in content or '比如' in content or '如' in content[:100]:
            return SegmentType.EXAMPLE
        
        # 检查论证
        for pattern, _ in self.assertion_patterns:
            if pattern.search(content[:50]):
                return SegmentType.ARGUMENT
        
        return SegmentType.GENERAL
    
    def _extract_entities(self, content: str) -> List[Entity]:
        """提取实体"""
        entities = []
        
        # 数字实体
        for match in self.number_pattern.finditer(content):
            entities.append(Entity(
                text=match.group(),
                entity_type=EntityType.NUMBER,
                start=match.start(),
                end=match.end(),
            ))
        
        # 日期实体
        for match in self.date_pattern.finditer(content):
            entities.append(Entity(
                text=match.group(),
                entity_type=EntityType.DATE,
                start=match.start(),
                end=match.end(),
            ))
        
        # 人名
        for match in self.person_pattern.finditer(content):
            text = match.group().strip()
            if len(text) >= 2:
                entities.append(Entity(
                    text=text,
                    entity_type=EntityType.PERSON,
                    start=match.start(),
                    end=match.end(),
                ))
        
        # 组织
        for match in self.org_pattern.finditer(content):
            entities.append(Entity(
                text=match.group().strip(),
                entity_type=EntityType.ORGANIZATION,
                start=match.start(),
                end=match.end(),
            ))
        
        # 地点
        for match in self.location_pattern.finditer(content):
            entities.append(Entity(
                text=match.group().strip(),
                entity_type=EntityType.LOCATION,
                start=match.start(),
                end=match.end(),
            ))
        
        # 技术术语
        for match in self.tech_pattern.finditer(content):
            entities.append(Entity(
                text=match.group(),
                entity_type=EntityType.TECHNOLOGY,
                start=match.start(),
                end=match.end(),
            ))
        
        # 去重
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e.text, e.entity_type)
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)
        
        return unique_entities
    
    def _extract_relations(
        self,
        content: str,
        entities: List[Entity]
    ) -> List[Relation]:
        """提取关系"""
        relations = []
        
        # 提取关键断言关系
        for pattern, rel_type in self.assertion_patterns:
            matches = pattern.finditer(content)
            for match in matches:
                # 找最近的实体
                nearby_entities = [
                    e for e in entities
                    if abs(e.start - match.start()) < 100
                ]
                
                if nearby_entities:
                    for e in nearby_entities[:2]:
                        relations.append(Relation(
                            source=e.text,
                            target=content[match.start():match.start()+30].strip(),
                            relation_type=rel_type,
                        ))
        
        return relations[:10]  # 限制数量
    
    def _extract_key_points(self, content: str) -> List[str]:
        """提取关键点"""
        key_points = []
        
        # 提取断言句
        sentences = re.split(r'[。！？；\n]', content)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 10:
                continue
            
            # 检查关键断言
            for pattern, _ in self.assertion_patterns:
                if pattern.search(sent):
                    if len(sent) < 100:
                        key_points.append(sent)
                    else:
                        key_points.append(sent[:100] + '...')
                    break
        
        return key_points[:5]
    
    def _summarize(self, content: str) -> str:
        """生成摘要"""
        # 取第一段或前100字
        first_para = content.split('\n\n')[0]
        if len(first_para) > 100:
            return first_para[:100] + '...'
        return first_para
    
    def _generate_questions(self, chunk: Chunk, content_type: SegmentType) -> List[str]:
        """生成追问"""
        questions = []
        
        # 根据内容类型生成
        if content_type == SegmentType.DEFINITION:
            questions.append("这个定义还有其他例子吗？")
            questions.append("这个概念和什么相关？")
        
        elif content_type == SegmentType.EXAMPLE:
            questions.append("这个例子说明了什么？")
            questions.append("还有其他类似的例子吗？")
        
        elif content_type == SegmentType.CODE:
            questions.append("这段代码的输入输出是什么？")
            questions.append("有什么需要注意的边界情况？")
        
        elif content_type == SegmentType.DATA:
            questions.append("这些数据的变化趋势是什么？")
            questions.append("数据来源可靠吗？")
        
        elif content_type == SegmentType.CONCLUSION:
            questions.append("这个结论的依据是什么？")
            questions.append("有什么局限性吗？")
        
        else:
            questions.append("这部分内容的主要观点是什么？")
            questions.append("需要我详细解释吗？")
        
        return questions[:3]
    
    def _assess_complexity(self, content: str) -> float:
        """评估复杂度"""
        # 基于多个因素
        factors = []
        
        # 长度因素
        length_score = min(len(content) / 2000, 1.0)
        factors.append(length_score)
        
        # 技术术语密度
        tech_count = len(self.tech_pattern.findall(content))
        tech_score = min(tech_count / 10, 1.0)
        factors.append(tech_score)
        
        # 句子嵌套
        nested = content.count('(') + content.count('（')
        nested_score = min(nested / 10, 1.0)
        factors.append(nested_score)
        
        return sum(factors) / len(factors) if factors else 0.5
    
    def _assess_quality(self, content: str, content_type: SegmentType) -> float:
        """评估质量"""
        score = 0.5
        
        # 长度适中
        if 100 < len(content) < 2000:
            score += 0.1
        
        # 有标点
        if content.count('。') >= 2:
            score += 0.1
        
        # 无乱码
        if not re.search(r'[■□▪▫◆◇]', content):
            score += 0.1
        
        # 有实质内容
        meaningful = re.sub(r'\s+', '', content)
        if len(meaningful) > len(content) * 0.8:
            score += 0.2
        
        return min(score, 1.0)
    
    def _analyze_cross_chunk_relations(
        self,
        chunks: List[Chunk],
        analyses: List[ChunkAnalysis]
    ) -> List[Relation]:
        """分析跨分块关系"""
        relations = []
        
        for i in range(len(chunks) - 1):
            curr = chunks[i]
            next_chunk = chunks[i + 1]
            
            # 基于关键词的关系
            overlap = set(curr.keywords) & set(next_chunk.keywords)
            if len(overlap) >= 2:
                relations.append(Relation(
                    source=f"chunk_{i}",
                    target=f"chunk_{i+1}",
                    relation_type="sequential",
                    confidence=len(overlap) / max(len(curr.keywords), 1),
                ))
            
            # 基于实体的关系
            curr_entities = {e.text for e in analyses[i].entities}
            next_entities = {e.text for e in analyses[i + 1].entities}
            shared = curr_entities & next_entities
            if shared:
                for e in list(shared)[:3]:
                    relations.append(Relation(
                        source=e,
                        target=f"chunk_{i+1}",
                        relation_type="mentioned_in",
                    ))
        
        return relations
    
    def _merge_global_entities(self, analyses: List[ChunkAnalysis]) -> List[Entity]:
        """合并全局实体"""
        seen = {}
        for analysis in analyses:
            for entity in analysis.entities:
                key = (entity.text, entity.entity_type)
                if key not in seen:
                    seen[key] = entity
                else:
                    # 合并置信度
                    seen[key].confidence = max(seen[key].confidence, entity.confidence)
        
        return list(seen.values())
    
    def _merge_global_relations(
        self,
        analyses: List[ChunkAnalysis],
        cross_relations: List[Relation]
    ) -> List[Relation]:
        """合并全局关系"""
        all_relations = []
        
        for analysis in analyses:
            all_relations.extend(analysis.relations)
        
        all_relations.extend(cross_relations)
        
        # 去重
        seen = set()
        unique = []
        for r in all_relations:
            key = (r.source, r.target, r.relation_type)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        
        return unique
    
    def _generate_overall_summary(self, analyses: List[ChunkAnalysis]) -> str:
        """生成整体摘要"""
        if not analyses:
            return ""
        
        # 取每个分块的摘要
        summaries = [a.summary for a in analyses if a.summary]
        
        if not summaries:
            return "内容分析完成，未提取到有效摘要。"
        
        # 取前两个摘要拼接
        return " | ".join(summaries[:2])
    
    def _extract_themes(self, analyses: List[ChunkAnalysis]) -> List[str]:
        """提取主题"""
        # 基于高频关键词
        keyword_freq = defaultdict(int)
        for analysis in analyses:
            for kw in analysis.metadata.get("keywords", []):
                keyword_freq[kw] += 1
        
        # 取频率最高的
        top = sorted(keyword_freq.items(), key=lambda x: -x[1])[:10]
        return [kw for kw, _ in top]
    
    def _generate_insights(
        self,
        analyses: List[ChunkAnalysis],
        themes: List[str]
    ) -> List[str]:
        """生成洞察"""
        insights = []
        
        # 基于内容类型分布
        type_counts = defaultdict(int)
        for a in analyses:
            type_counts[a.content_type] += 1
        
        most_common_type = max(type_counts.items(), key=lambda x: x[1])
        insights.append(f"内容以 {most_common_type[0].value} 类型为主（{most_common_type[1]} 处）")
        
        # 基于主题
        if themes:
            insights.append(f"核心主题：{', '.join(themes[:3])}")
        
        # 基于复杂度
        avg_complexity = sum(a.complexity for a in analyses) / len(analyses)
        if avg_complexity > 0.7:
            insights.append("内容复杂度较高，需要深入分析")
        elif avg_complexity < 0.4:
            insights.append("内容相对简单，容易理解")
        
        return insights
    
    def _generate_recommended_questions(
        self,
        analyses: List[ChunkAnalysis]
    ) -> List[str]:
        """生成推荐追问"""
        questions = []
        
        for analysis in analyses:
            if analysis.quality > 0.6 and analysis.questions:
                questions.extend(analysis.questions[:1])
        
        return list(set(questions))[:5]


def analyze_chunk(chunk: Chunk, depth: str = "standard") -> ChunkAnalysis:
    """
    便捷分析函数
    
    Args:
        chunk: 分块
        depth: 分析深度
    
    Returns:
        ChunkAnalysis: 分析结果
    """
    analyzer = ChunkAnalyzer(depth=AnalysisDepth(depth))
    return analyzer.analyze_chunk(chunk)
