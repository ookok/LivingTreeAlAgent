# -*- coding: utf-8 -*-
"""
语义索引 - AI原生OS愿景 Phase 1-3

虚拟文件系统（Virtual File System）实现：
- 将上下文组织成语义相关的文件/目录结构
- 每个"文件"有语义标签和索引
- 支持基于语义的自然语言查询
- 快速定位相关内容（懒加载）

Author: AI Native OS Team
Date: 2026-04-24
"""

import re
import hashlib
import time
from typing import Dict, List, Optional, Any, Tuple, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from collections import defaultdict


def _defaultdict_set():
    return defaultdict(set)


class NodeType(Enum):
    """节点类型"""
    FILE = "file"           # 文件节点
    DIRECTORY = "directory" # 目录节点
    LINK = "link"          # 链接节点
    TAG = "tag"            # 标签节点


@dataclass
class SemanticChunk:
    """语义块"""
    id: str
    content: str
    node_type: NodeType = NodeType.FILE
    path: str = ""
    semantic_tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    intent_types: List[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0
    char_start: int = 0
    char_end: int = 0
    importance: float = 1.0  # 重要性评分 0-1
    dependencies: List[str] = field(default_factory=list)  # 依赖的其他块ID
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if not isinstance(other, SemanticChunk):
            return False
        return self.id == other.id


@dataclass
class SearchResult:
    """搜索结果"""
    chunk: SemanticChunk
    relevance_score: float  # 相关度评分 0-1
    match_reason: str       # 匹配原因
    context_preview: str    # 上下文预览


@dataclass
class VirtualFileSystem:
    """虚拟文件系统"""
    root_path: str = "/context"
    nodes: Dict[str, SemanticChunk] = field(default_factory=dict)
    paths: Dict[str, str] = field(default_factory=dict)  # path -> chunk_id
    tag_index: Dict[str, Set[str]] = field(default_factory=_defaultdict_set)  # tag -> chunk_ids
    keyword_index: Dict[str, Set[str]] = field(default_factory=_defaultdict_set)  # keyword -> chunk_ids
    intent_index: Dict[str, Set[str]] = field(default_factory=_defaultdict_set)  # intent -> chunk_ids
    parent_child: Dict[str, Set[str]] = field(default_factory=_defaultdict_set)  # parent_id -> child_ids
    
    # 统计信息
    total_chunks: int = 0
    total_chars: int = 0
    index_time_ms: float = 0.0
    
    def add_chunk(self, chunk: SemanticChunk) -> None:
        """添加语义块"""
        self.nodes[chunk.id] = chunk
        self.paths[chunk.path] = chunk.id
        self.total_chunks += 1
        self.total_chars += len(chunk.content)
        
        # 索引标签
        for tag in chunk.semantic_tags:
            if tag.lower() not in self.tag_index:
                self.tag_index[tag.lower()] = set()
            self.tag_index[tag.lower()].add(chunk.id)
        
        # 索引关键词
        for keyword in chunk.keywords:
            if keyword.lower() not in self.keyword_index:
                self.keyword_index[keyword.lower()] = set()
            self.keyword_index[keyword.lower()].add(chunk.id)
        
        # 索引意图类型
        for intent in chunk.intent_types:
            if intent.lower() not in self.intent_index:
                self.intent_index[intent.lower()] = set()
            self.intent_index[intent.lower()].add(chunk.id)
    
    def get_chunk(self, chunk_id: str) -> Optional[SemanticChunk]:
        """获取语义块"""
        return self.nodes.get(chunk_id)
    
    def get_chunk_by_path(self, path: str) -> Optional[SemanticChunk]:
        """通过路径获取语义块"""
        chunk_id = self.paths.get(path)
        return self.nodes.get(chunk_id) if chunk_id else None
    
    def get_children(self, parent_id: str) -> List[SemanticChunk]:
        """获取子节点"""
        child_ids = self.parent_child.get(parent_id, set())
        return [self.nodes[cid] for cid in child_ids if cid in self.nodes]
    
    def search(self, query: str, intent_hint: str = "", 
               max_results: int = 10) -> List[SearchResult]:
        """语义搜索"""
        results = []
        query_lower = query.lower()
        query_terms = self._tokenize(query_lower)
        
        # 计算每个块的得分
        scored_chunks: Dict[str, float] = {}
        
        for chunk_id, chunk in self.nodes.items():
            score = 0.0
            reasons = []
            
            # 1. 标签匹配
            tag_score = self._calculate_tag_score(query_terms, chunk)
            score += tag_score * 0.3
            if tag_score > 0:
                reasons.append(f"标签匹配 ({tag_score:.2f})")
            
            # 2. 关键词匹配
            keyword_score = self._calculate_keyword_score(query_terms, chunk)
            score += keyword_score * 0.3
            if keyword_score > 0:
                reasons.append(f"关键词匹配 ({keyword_score:.2f})")
            
            # 3. 内容匹配
            content_score = self._calculate_content_score(query_lower, chunk)
            score += content_score * 0.25
            if content_score > 0:
                reasons.append(f"内容匹配 ({content_score:.2f})")
            
            # 4. 意图匹配
            if intent_hint:
                intent_score = self._calculate_intent_score(intent_hint, chunk)
                score += intent_score * 0.15
                if intent_score > 0:
                    reasons.append(f"意图匹配 ({intent_score:.2f})")
            
            # 5. 重要性加权
            score *= (0.5 + 0.5 * chunk.importance)
            
            if score > 0:
                scored_chunks[chunk_id] = score
        
        # 排序并返回 Top N
        sorted_chunks = sorted(scored_chunks.items(), key=lambda x: x[1], reverse=True)
        
        for chunk_id, score in sorted_chunks[:max_results]:
            chunk = self.nodes[chunk_id]
            results.append(SearchResult(
                chunk=chunk,
                relevance_score=min(score, 1.0),
                match_reason="; ".join(reasons[:2]),
                context_preview=self._generate_preview(chunk.content, query_lower)
            ))
        
        return results
    
    def search_by_tag(self, tag: str) -> List[SemanticChunk]:
        """通过标签搜索"""
        tag_lower = tag.lower()
        chunk_ids = self.tag_index.get(tag_lower, set())
        return [self.nodes[cid] for cid in chunk_ids if cid in self.nodes]
    
    def search_by_path_pattern(self, pattern: str) -> List[SemanticChunk]:
        """通过路径模式搜索"""
        results = []
        pattern_lower = pattern.lower()
        
        for path, chunk_id in self.paths.items():
            if pattern_lower in path.lower():
                chunk = self.nodes.get(chunk_id)
                if chunk:
                    results.append(chunk)
        
        return results
    
    def get_related_chunks(self, chunk_id: str, depth: int = 1) -> List[SemanticChunk]:
        """获取相关块（依赖关系）"""
        related = []
        visited = {chunk_id}
        
        def traverse(cid: str, current_depth: int):
            if current_depth > depth:
                return
            
            chunk = self.nodes.get(cid)
            if not chunk:
                return
            
            # 添加依赖的块
            for dep_id in chunk.dependencies:
                if dep_id not in visited and dep_id in self.nodes:
                    visited.add(dep_id)
                    related.append(self.nodes[dep_id])
                    traverse(dep_id, current_depth + 1)
        
        traverse(chunk_id, 0)
        return related
    
    def _tokenize(self, text: str) -> Set[str]:
        """分词"""
        # 简单分词：中文按字符，英文按单词
        tokens = set()
        
        # 英文单词
        english_words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text)
        tokens.update(w.lower() for w in english_words if len(w) > 2)
        
        # 中文词组（简单按2-4字切分）
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
        tokens.update(c.lower() for c in chinese_chars)
        
        return tokens
    
    def _calculate_tag_score(self, query_terms: Set[str], chunk: SemanticChunk) -> float:
        """计算标签得分"""
        if not chunk.semantic_tags:
            return 0.0
        
        chunk_tags = {t.lower() for t in chunk.semantic_tags}
        matches = len(query_terms & chunk_tags)
        return matches / len(chunk_tags) if chunk_tags else 0.0
    
    def _calculate_keyword_score(self, query_terms: Set[str], chunk: SemanticChunk) -> float:
        """计算关键词得分"""
        if not chunk.keywords:
            return 0.0
        
        chunk_keywords = {k.lower() for k in chunk.keywords}
        matches = len(query_terms & chunk_keywords)
        return matches / len(chunk_keywords) if chunk_keywords else 0.0
    
    def _calculate_content_score(self, query: str, chunk: SemanticChunk) -> float:
        """计算内容得分"""
        content_lower = chunk.content.lower()
        
        # 精确匹配
        if query in content_lower:
            return 1.0
        
        # 部分匹配
        matches = sum(1 for term in query.split() if term in content_lower)
        return matches / len(query.split()) if query.split() else 0.0
    
    def _calculate_intent_score(self, intent: str, chunk: SemanticChunk) -> float:
        """计算意图得分"""
        intent_lower = intent.lower()
        
        # 检查意图类型匹配
        for chunk_intent in chunk.intent_types:
            if intent_lower in chunk_intent.lower() or chunk_intent.lower() in intent_lower:
                return 1.0
        
        # 检查标签中的意图
        for tag in chunk.semantic_tags:
            if intent_lower in tag.lower():
                return 0.5
        
        return 0.0
    
    def _generate_preview(self, content: str, query: str, max_len: int = 150) -> str:
        """生成预览"""
        content_lower = content.lower()
        query_lower = query.lower()
        
        # 找到匹配位置
        pos = content_lower.find(query_lower)
        if pos == -1:
            # 尝试找到关键词位置
            for term in query_lower.split():
                pos = content_lower.find(term)
                if pos != -1:
                    break
        
        if pos == -1:
            pos = 0
        
        # 提取上下文窗口
        start = max(0, pos - 50)
        end = min(len(content), pos + max_len)
        
        preview = content[start:end]
        
        # 添加省略号
        if start > 0:
            preview = "..." + preview
        if end < len(content):
            preview = preview + "..."
        
        return preview.strip()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_chunks": self.total_chunks,
            "total_chars": self.total_chars,
            "total_tags": len(self.tag_index),
            "total_keywords": len(self.keyword_index),
            "total_intents": len(self.intent_index),
            "index_time_ms": self.index_time_ms,
        }


# ============================================================================
# 语义索引构建器
# ============================================================================

class SemanticIndexer:
    """
    语义索引构建器
    
    将压缩后的上下文转换为虚拟文件系统结构。
    """
    
    # 停用词
    STOP_WORDS = {
        '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
        '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
        'this', 'that', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'may', 'might', 'must', 'can', 'need', 'to', 'of', 'in', 'for', 'on', 'with',
        'at', 'by', 'from', 'as', 'into', 'through', 'during', 'before', 'after',
        'and', 'or', 'but', 'if', 'because', 'while', 'although', 'so', 'that'
    }
    
    def __init__(self, 
                 max_chunk_size: int = 500,
                 overlap_size: int = 50,
                 min_chunk_size: int = 50):
        """
        初始化
        
        Args:
            max_chunk_size: 最大块大小（字符数）
            overlap_size: 块之间的重叠大小
            min_chunk_size: 最小块大小
        """
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.min_chunk_size = min_chunk_size
    
    def index(self, context: str, intent_signature: Optional[Dict] = None,
              metadata: Optional[Dict] = None) -> VirtualFileSystem:
        """
        构建语义索引
        
        Args:
            context: 待索引的上下文
            intent_signature: 意图签名
            metadata: 元数据
        
        Returns:
            VirtualFileSystem: 虚拟文件系统
        """
        start_time = time.time()
        metadata = metadata or {}
        intent_signature = intent_signature or {}
        
        vfs = VirtualFileSystem()
        
        # 1. 检测内容类型
        content_type = self._detect_content_type(context)
        
        # 2. 根据内容类型分块
        if content_type == "code":
            chunks = self._index_code(context, intent_signature, metadata)
        elif content_type == "markdown":
            chunks = self._index_markdown(context, intent_signature, metadata)
        elif content_type == "mixed":
            chunks = self._index_mixed(context, intent_signature, metadata)
        else:
            chunks = self._index_plain_text(context, intent_signature, metadata)
        
        # 3. 添加到 VFS
        for chunk in chunks:
            vfs.add_chunk(chunk)
        
        # 4. 建立依赖关系
        self._build_dependencies(vfs)
        
        vfs.index_time_ms = (time.time() - start_time) * 1000
        
        return vfs
    
    def _detect_content_type(self, context: str) -> str:
        """检测内容类型"""
        code_block_ratio = len(re.findall(r'```[\w]*\n', context)) / max(1, len(context) / 1000)
        
        if code_block_ratio > 0.1:
            return "code"
        
        markdown_headings = len(re.findall(r'^#{1,6}\s+', context, re.MULTILINE))
        if markdown_headings > 2:
            return "markdown"
        
        if '```' in context or '`' in context:
            return "mixed"
        
        return "plain_text"
    
    def _index_code(self, context: str, intent_sig: Dict, metadata: Dict) -> List[SemanticChunk]:
        """索引代码内容"""
        chunks = []
        
        # 提取代码块
        code_block_pattern = r'```(\w+)?\n(.*?)```'
        code_blocks = list(re.finditer(code_block_pattern, context, re.DOTALL))
        
        for i, match in enumerate(code_blocks):
            lang = match.group(1) or "unknown"
            code = match.group(2)
            
            # 提取函数/类签名
            signatures = self._extract_signatures(code, lang)
            
            chunk = SemanticChunk(
                id=f"code_block_{i+1}",
                content=code.strip(),
                node_type=NodeType.FILE,
                path=f"/code/{lang}/block_{i+1}",
                semantic_tags=[lang, "code", "implementation"],
                keywords=signatures,
                intent_types=[intent_sig.get('type', 'modify')],
                line_start=context[:match.start()].count('\n') + 1,
                line_end=context[:match.end()].count('\n'),
                importance=self._calculate_importance(code, signatures)
            )
            chunks.append(chunk)
        
        # 添加代码目录
        if chunks:
            dir_chunk = SemanticChunk(
                id="code_directory",
                content=f"代码段目录 ({len(chunks)} 个代码块)",
                node_type=NodeType.DIRECTORY,
                path="/code",
                semantic_tags=["code", "directory"],
                importance=0.3
            )
            chunks.insert(0, dir_chunk)
        
        return chunks
    
    def _index_markdown(self, context: str, intent_sig: Dict, metadata: Dict) -> List[SemanticChunk]:
        """索引 Markdown 内容"""
        chunks = []
        
        # 按标题分割
        heading_pattern = r'^(#{1,6})\s+(.+)$'
        lines = context.split('\n')
        
        current_section = None
        current_content = []
        current_level = 0
        
        for i, line in enumerate(lines):
            match = re.match(heading_pattern, line)
            
            if match:
                # 保存之前的 section
                if current_section and current_content:
                    content = '\n'.join(current_content).strip()
                    if len(content) >= self.min_chunk_size:
                        chunk = self._create_markdown_chunk(
                            current_section, content, current_level, intent_sig, len(chunks)
                        )
                        chunks.append(chunk)
                
                # 开始新 section
                current_level = len(match.group(1))
                current_section = match.group(2)
                current_content = []
            else:
                current_content.append(line)
        
        # 保存最后一个 section
        if current_section and current_content:
            content = '\n'.join(current_content).strip()
            if len(content) >= self.min_chunk_size:
                chunk = self._create_markdown_chunk(
                    current_section, content, current_level, intent_sig, len(chunks)
                )
                chunks.append(chunk)
        
        # 添加根目录
        dir_chunk = SemanticChunk(
            id="docs_directory",
            content=f"文档目录 ({len(chunks)} 个章节)",
            node_type=NodeType.DIRECTORY,
            path="/docs",
            semantic_tags=["documentation", "directory"],
            importance=0.3
        )
        chunks.insert(0, dir_chunk)
        
        return chunks
    
    def _create_markdown_chunk(self, title: str, content: str, level: int,
                               intent_sig: Dict, index: int) -> SemanticChunk:
        """创建 Markdown 块"""
        # 提取标签
        tags = self._extract_tags_from_content(content)
        tags.extend(["documentation", f"heading_level_{level}"])
        
        # 提取关键词
        keywords = self._extract_keywords(content)
        
        # 计算重要性（标题级别越高越重要）
        importance = 1.0 - (level - 1) * 0.15
        
        return SemanticChunk(
            id=f"section_{index+1}",
            content=f"# {'#' * level} {title}\n\n{content}",
            node_type=NodeType.FILE,
            path=f"/docs/{title[:30].replace('/', '_')}",
            semantic_tags=tags,
            keywords=keywords,
            intent_types=[intent_sig.get('type', 'analyze')],
            importance=importance
        )
    
    def _index_mixed(self, context: str, intent_sig: Dict, metadata: Dict) -> List[SemanticChunk]:
        """索引混合内容"""
        chunks = []
        
        # 分离代码块和非代码块
        parts = re.split(r'(```[\w]*\n.*?```)', context, flags=re.DOTALL)
        
        current_path = "/mixed"
        
        for i, part in enumerate(parts):
            if part.startswith('```'):
                # 代码块
                match = re.match(r'```(\w+)?\n(.*?)```', part, re.DOTALL)
                if match:
                    lang = match.group(1) or "code"
                    code = match.group(2)
                    signatures = self._extract_signatures(code, lang)
                    
                    chunk = SemanticChunk(
                        id=f"code_{i}",
                        content=code.strip(),
                        node_type=NodeType.FILE,
                        path=f"/mixed/code_{i}",
                        semantic_tags=[lang, "code"],
                        keywords=signatures,
                        intent_types=[intent_sig.get('type', 'modify')],
                        importance=0.8
                    )
                    chunks.append(chunk)
            else:
                # 文本内容
                part = part.strip()
                if len(part) >= self.min_chunk_size:
                    keywords = self._extract_keywords(part)
                    tags = self._extract_tags_from_content(part)
                    
                    chunk = SemanticChunk(
                        id=f"text_{i}",
                        content=part,
                        node_type=NodeType.FILE,
                        path=f"/mixed/text_{i}",
                        semantic_tags=tags,
                        keywords=keywords,
                        intent_types=[intent_sig.get('type', 'analyze')],
                        importance=0.6
                    )
                    chunks.append(chunk)
        
        return chunks
    
    def _index_plain_text(self, context: str, intent_sig: Dict, metadata: Dict) -> List[SemanticChunk]:
        """索引纯文本"""
        chunks = []
        
        # 按段落分割
        paragraphs = [p.strip() for p in context.split('\n\n') if p.strip()]
        
        for i, para in enumerate(paragraphs):
            if len(para) < self.min_chunk_size:
                continue
            
            keywords = self._extract_keywords(para)
            tags = self._extract_tags_from_content(para)
            
            chunk = SemanticChunk(
                id=f"paragraph_{i+1}",
                content=para,
                node_type=NodeType.FILE,
                path=f"/text/para_{i+1}",
                semantic_tags=tags,
                keywords=keywords,
                intent_types=[intent_sig.get('type', 'analyze')],
                importance=0.5
            )
            chunks.append(chunk)
        
        return chunks
    
    def _extract_signatures(self, code: str, lang: str) -> List[str]:
        """提取代码签名"""
        signatures = []
        
        if lang in ('python', 'py'):
            # Python 函数和类
            funcs = re.findall(r'def\s+(\w+)\s*\(', code)
            classes = re.findall(r'class\s+(\w+)', code)
            signatures.extend(funcs)
            signatures.extend(classes)
        
        elif lang in ('javascript', 'js', 'typescript', 'ts'):
            # JavaScript 函数
            funcs = re.findall(r'(?:function\s+(\w+)|const\s+(\w+)\s*=|(\w+)\s*:\s*function)', code)
            classes = re.findall(r'class\s+(\w+)', code)
            for f in funcs:
                if isinstance(f, tuple):
                    signatures.extend([x for x in f if x])
                else:
                    signatures.append(f)
            signatures.extend(classes)
        
        elif lang in ('java', 'kotlin'):
            # Java 方法和类
            methods = re.findall(r'(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(', code)
            classes = re.findall(r'class\s+(\w+)', code)
            signatures.extend(methods)
            signatures.extend(classes)
        
        return list(set(signatures))
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 分词
        words = re.findall(r'[\u4e00-\u9fa5]{2,4}|[a-zA-Z_][a-zA-Z0-9_]*', text.lower())
        
        # 过滤停用词和太短的词
        keywords = [w for w in words if w not in self.STOP_WORDS and len(w) > 2]
        
        # 统计频率
        word_freq = {}
        for w in keywords:
            word_freq[w] = word_freq.get(w, 0) + 1
        
        # 返回高频词
        top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        return [w for w, _ in top_keywords]
    
    def _extract_tags_from_content(self, content: str) -> List[str]:
        """从内容中提取标签"""
        tags = []
        
        # 代码语言标签
        langs = re.findall(r'```(\w+)', content)
        tags.extend(langs)
        
        # 特殊标记
        if 'TODO' in content or 'FIXME' in content:
            tags.append('todo')
        if 'BUG' in content or 'ERROR' in content:
            tags.append('bug')
        if 'API' in content or '接口' in content:
            tags.append('api')
        if 'Config' in content or '配置' in content:
            tags.append('config')
        
        # 实体识别（简单实现）
        entities = re.findall(r'([A-Z][a-zA-Z]+(?:Error|Exception|Handler|Manager|Service|Controller))', content)
        tags.extend([e.lower() for e in entities])
        
        return list(set(tags))
    
    def _calculate_importance(self, code: str, signatures: List[str]) -> float:
        """计算代码重要性"""
        importance = 0.5
        
        # 有函数定义加重要性
        if 'def ' in code or 'function ' in code:
            importance += 0.2
        
        # 有类定义
        if 'class ' in code:
            importance += 0.2
        
        # 代码行数
        lines = code.count('\n')
        if lines > 50:
            importance += 0.1
        
        return min(importance, 1.0)
    
    def _build_dependencies(self, vfs: VirtualFileSystem) -> None:
        """建立依赖关系"""
        # 基于内容相似度建立依赖
        for chunk_id, chunk in vfs.nodes.items():
            if chunk.node_type == NodeType.DIRECTORY:
                continue
            
            for other_id, other_chunk in vfs.nodes.items():
                if chunk_id == other_id or other_chunk.node_type == NodeType.DIRECTORY:
                    continue
                
                # 检查是否相关
                if self._is_related(chunk, other_chunk):
                    chunk.dependencies.append(other_id)
                    # 建立父子关系
                    if other_chunk.node_type == NodeType.DIRECTORY:
                        if other_id not in vfs.parent_child:
                            vfs.parent_child[other_id] = set()
                        vfs.parent_child[other_id].add(chunk_id)
    
    def _is_related(self, chunk1: SemanticChunk, chunk2: SemanticChunk) -> bool:
        """判断两个块是否相关"""
        # 标签重叠
        tags1 = set(t.lower() for t in chunk1.semantic_tags)
        tags2 = set(t.lower() for t in chunk2.semantic_tags)
        if tags1 & tags2:
            return True
        
        # 关键词重叠
        keywords1 = set(k.lower() for k in chunk1.keywords)
        keywords2 = set(k.lower() for k in chunk2.keywords)
        if keywords1 & keywords2:
            return True
        
        return False


# ============================================================================
# 懒加载语义块
# ============================================================================

class LazySemanticLoader:
    """
    懒加载语义块
    
    只在需要时加载完整内容。
    """
    
    def __init__(self, vfs: VirtualFileSystem):
        self.vfs = vfs
        self.loaded_chunks: Set[str] = set()
    
    def load(self, chunk_id: str) -> Optional[SemanticChunk]:
        """加载语义块"""
        if chunk_id in self.loaded_chunks:
            return self.vfs.get_chunk(chunk_id)
        
        chunk = self.vfs.get_chunk(chunk_id)
        if chunk:
            self.loaded_chunks.add(chunk_id)
        
        return chunk
    
    def load_related(self, chunk_id: str, depth: int = 1) -> List[SemanticChunk]:
        """加载相关块"""
        chunks = []
        
        # 加载主块
        main_chunk = self.load(chunk_id)
        if main_chunk:
            chunks.append(main_chunk)
        
        # 加载相关块
        related = self.vfs.get_related_chunks(chunk_id, depth)
        for chunk in related:
            if chunk.id not in self.loaded_chunks:
                self.loaded_chunks.add(chunk.id)
                chunks.append(chunk)
        
        return chunks
    
    def search_and_load(self, query: str, intent_hint: str = "",
                       max_results: int = 5) -> List[SemanticChunk]:
        """搜索并加载"""
        results = self.vfs.search(query, intent_hint, max_results)
        
        chunks = []
        for result in results:
            if result.chunk.id not in self.loaded_chunks:
                self.loaded_chunks.add(result.chunk.id)
            chunks.append(result.chunk)
        
        return chunks


# ============================================================================
# 便捷函数
# ============================================================================

def create_semantic_index(context: str, intent_signature: Optional[Dict] = None,
                          metadata: Optional[Dict] = None) -> VirtualFileSystem:
    """
    创建语义索引
    
    用法:
        vfs = create_semantic_index(context, intent_sig)
        results = vfs.search("用户登录")
    """
    indexer = SemanticIndexer()
    return indexer.index(context, intent_signature, metadata)


def quick_search(vfs: VirtualFileSystem, query: str, 
                max_results: int = 5) -> List[SearchResult]:
    """
    快速搜索
    
    用法:
        results = quick_search(vfs, "登录函数")
    """
    return vfs.search(query, max_results=max_results)


def get_chunk_context(vfs: VirtualFileSystem, chunk_id: str,
                       related_depth: int = 1) -> str:
    """
    获取块的上下文
    
    用法:
        context = get_chunk_context(vfs, "section_1")
    """
    chunk = vfs.get_chunk(chunk_id)
    if not chunk:
        return ""
    
    loader = LazySemanticLoader(vfs)
    related = loader.load_related(chunk_id, related_depth)
    
    # 组合上下文
    contexts = [chunk.content]
    for r in related:
        if r.id != chunk_id:
            contexts.append(f"\n--- {r.path} ---\n{r.content}")
    
    return "\n".join(contexts)
