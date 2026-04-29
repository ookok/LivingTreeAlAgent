"""
LLM Wiki 模块 - KnowledgeGraph 集成器
========================================

Phase 2: 将 LLM Wiki 章节结构导入知识图谱

功能：
1. 将 DocumentChunk 转换为 KnowledgeNode
2. 建立章节层级关系（part_of）
3. 识别概念、方法、API 等实体
4. 导出为 KnowledgeGraph 格式

作者: LivingTreeAI Team
日期: 2026-04-29
版本: 2.0.0 (Phase 2)
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from loguru import logger

# 导入 Phase 1 的数据模型
from .models import DocumentChunk

# 导入 KnowledgeGraph 核心类
from client.src.business.knowledge_graph.graph import (
    KnowledgeGraph,
    KnowledgeNode,
    KnowledgeRelation
)


@dataclass
class WikiNodeMapping:
    """Wiki 节点映射"""
    chunk_id: str
    node_id: str
    title: str
    node_type: str
    chunk: DocumentChunk


class LLMWikiKnowledgeGraphIntegrator:
    """
    LLM Wiki → KnowledgeGraph 集成器
    
    将 Phase 1 解析的 DocumentChunk 转换为 KnowledgeGraph 的节点和关系。
    """
    
    def __init__(self, domain: str = "llm_wiki"):
        """初始化集成器"""
        self.domain = domain
        self.graph = KnowledgeGraph()
        self.node_mappings: List[WikiNodeMapping] = []
        
        # 章节层级跟踪
        self._section_stack: List[Tuple[str, str]] = []  # (title, node_id)
        
        logger.info(f"LLMWikiKnowledgeGraphIntegrator 初始化完成 (domain={domain})")
    
    def integrate_chunks(self, chunks: List[DocumentChunk]) -> KnowledgeGraph:
        """
        将 DocumentChunk 列表集成到 KnowledgeGraph
        
        Args:
            chunks: Phase 1 解析的文档块列表
            
        Returns:
            KnowledgeGraph 实例
        """
        logger.info(f"开始集成 {len(chunks)} 个文档块到知识图谱")
        
        # 1. 按 source 分组（每个文件一个子图）
        chunks_by_source = self._group_by_source(chunks)
        
        for source, source_chunks in chunks_by_source.items():
            logger.info(f"处理文档: {source} ({len(source_chunks)} 个块)")
            self._integrate_document(source, source_chunks)
        
        # 2. 建立跨文档关系（可选）
        self._link_cross_references()
        
        logger.info(f"集成完成: {len(self.graph.nodes)} 个节点, {len(self.graph.relations)} 个关系")
        return self.graph
    
    def _group_by_source(self, chunks: List[DocumentChunk]) -> Dict[str, List[DocumentChunk]]:
        """按 source 分组"""
        groups = {}
        for chunk in chunks:
            source = chunk.source or "unknown"
            if source not in groups:
                groups[source] = []
            groups[source].append(chunk)
        return groups
    
    def _integrate_document(self, source: str, chunks: List[DocumentChunk]) -> None:
        """集成单个文档"""
        # 重置章节栈
        self._section_stack = []
        
        # 按 chunk_type 分类处理
        for chunk in chunks:
            if chunk.chunk_type == "text":
                self._process_text_chunk(source, chunk)
            elif chunk.chunk_type == "code":
                self._process_code_chunk(source, chunk)
            elif chunk.chunk_type == "api":
                self._process_api_chunk(source, chunk)
            else:
                self._process_generic_chunk(source, chunk)
    
    def _process_text_chunk(self, source: str, chunk: DocumentChunk) -> None:
        """处理文本块（识别章节层级）"""
        title = chunk.title or "Untitled"
        
        # 判断章节层级（从 section 字段提取 # 数量）
        level = self._detect_heading_level(chunk.section)
        
        # 创建节点
        node_type = self._map_chunk_type_to_node_type(chunk.chunk_type, level)
        node = self._create_node(title, chunk.content, node_type, chunk)
        
        # 建立层级关系
        if level > 0 and self._section_stack:
            # 找到父章节
            parent_id = self._find_parent(level)
            if parent_id:
                self._add_relation(node.node_id, "part_of", parent_id)
        
        # 更新章节栈
        self._update_section_stack(level, title, node.node_id)
        
        # 提取概念（从文本中识别关键术语）
        self._extract_concepts(chunk.content, node.node_id)
    
    def _process_code_chunk(self, source: str, chunk: DocumentChunk) -> None:
        """处理代码块"""
        title = chunk.title or f"Code Block ({chunk.metadata.get('language', 'unknown')})"
        
        node = self._create_node(
            title=title,
            content=chunk.content,
            node_type="code_example",
            chunk=chunk
        )
        
        # 如果有父章节，建立关系
        if self._section_stack:
            parent_id = self._section_stack[-1][1]
            self._add_relation(node.node_id, "part_of", parent_id)
    
    def _process_api_chunk(self, source: str, chunk: DocumentChunk) -> None:
        """处理 API 定义块"""
        title = chunk.title or "API Definition"
        
        node = self._create_node(
            title=title,
            content=chunk.content,
            node_type="api_interface",
            chunk=chunk
        )
        
        # 如果有父章节，建立关系
        if self._section_stack:
            parent_id = self._section_stack[-1][1]
            self._add_relation(node.node_id, "part_of", parent_id)
    
    def _process_generic_chunk(self, source: str, chunk: DocumentChunk) -> None:
        """处理通用块"""
        title = chunk.title or f"Chunk ({chunk.chunk_type})"
        
        node = self._create_node(
            title=title,
            content=chunk.content,
            node_type="generic",
            chunk=chunk
        )
        
        # 如果有父章节，建立关系
        if self._section_stack:
            parent_id = self._section_stack[-1][1]
            self._add_relation(node.node_id, "part_of", parent_id)
    
    def _create_node(self, title: str, content: str, node_type: str, chunk: DocumentChunk) -> KnowledgeNode:
        """创建 KnowledgeNode"""
        node = KnowledgeNode(
            title=title,
            content=content[:500],  # 限制内容长度
            node_type=node_type,
            domain=self.domain,
            properties={
                "source": chunk.source,
                "chunk_type": chunk.chunk_type,
                "section": chunk.section,
                "metadata": chunk.metadata,
                "full_content": content  # 完整内容（不存入节点，仅用于检索）
            }
        )
        
        # 添加到图谱
        self.graph.add_node(node)
        
        # 记录映射
        mapping = WikiNodeMapping(
            chunk_id=self._generate_chunk_id(chunk),
            node_id=node.node_id,
            title=title,
            node_type=node_type,
            chunk=chunk
        )
        self.node_mappings.append(mapping)
        
        logger.debug(f"创建节点: {title} ({node_type})")
        return node
    
    def _add_relation(self, source_id: str, relation_type: str, target_id: str, weight: float = 1.0) -> None:
        """添加关系"""
        relation = KnowledgeRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            weight=weight
        )
        self.graph.add_relation(relation)
        logger.debug(f"添加关系: {source_id} -[{relation_type}]-> {target_id}")
    
    def _detect_heading_level(self, section: str) -> int:
        """检测标题层级（# 数量）"""
        if not section:
            return 0
        
        # 匹配开头的 # 数量
        match = re.match(r"^(#+) ", section)
        if match:
            return len(match.group(1))
        
        return 0
    
    def _map_chunk_type_to_node_type(self, chunk_type: str, heading_level: int) -> str:
        """映射 chunk_type 到 node_type"""
        if chunk_type == "text":
            if heading_level == 1:
                return "chapter"
            elif heading_level == 2:
                return "section"
            elif heading_level >= 3:
                return "subsection"
            else:
                return "concept"
        elif chunk_type == "code":
            return "code_example"
        elif chunk_type == "api":
            return "api_interface"
        elif chunk_type == "example":
            return "example"
        else:
            return "generic"
    
    def _find_parent(self, current_level: int) -> Optional[str]:
        """找到当前章节的父章节"""
        if not self._section_stack:
            return None
        
        # 栈顶是最近添加的章节
        # 需要找到层级小于当前层级的章节
        for i in range(len(self._section_stack) - 1, -1, -1):
            parent_level = self._detect_heading_level(self._section_stack[i][0])
            if parent_level < current_level:
                return self._section_stack[i][1]
        
        return None
    
    def _update_section_stack(self, level: int, title: str, node_id: str) -> None:
        """更新章节栈"""
        if level == 0:
            return
        
        # 移除同级或更深的章节
        while self._section_stack:
            top_level = self._detect_heading_level(self._section_stack[-1][0])
            if top_level >= level:
                self._section_stack.pop()
            else:
                break
        
        # 添加当前章节
        self._section_stack.append((title, node_id))
    
    def _extract_concepts(self, text: str, context_node_id: str) -> None:
        """从文本中提取概念（简单版：提取加粗术语）"""
        # 匹配 **术语** 或 `代码术语`
        bold_terms = re.findall(r"\*\*(.+?)\*\*", text)
        code_terms = re.findall(r"`([^`]+)`", text)
        
        all_terms = bold_terms + code_terms
        
        for term in set(all_terms):
            if len(term) < 3 or len(term) > 50:
                continue
            
            # 创建概念节点
            concept_node = KnowledgeNode(
                title=term,
                content=f"概念: {term}",
                node_type="concept",
                domain=self.domain,
                properties={
                    "extracted_from": context_node_id,
                    "extraction_method": "bold_or_code"
                }
            )
            self.graph.add_node(concept_node)
            
            # 建立关系
            self._add_relation(context_node_id, "mentions", concept_node.node_id, weight=0.8)
    
    def _link_cross_references(self) -> None:
        """建立跨文档引用关系（可选，高级功能）"""
        # TODO: 实现跨文档引用检测
        # 例如：检测 "参见 Chapter 2" 这样的引用
        pass
    
    def _generate_chunk_id(self, chunk: DocumentChunk) -> str:
        """生成 chunk 的唯一 ID"""
        import hashlib
        content_hash = hashlib.md5(chunk.content.encode()).hexdigest()[:8]
        return f"{chunk.chunk_type}_{content_hash}"
    
    def get_graph(self) -> KnowledgeGraph:
        """获取知识图谱"""
        return self.graph
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.graph.get_statistics()
        stats["domain"] = self.domain
        stats["node_mappings"] = len(self.node_mappings)
        return stats
    
    def export_to_json(self) -> str:
        """导出为 JSON"""
        import json
        data = {
            "nodes": [{
                "node_id": node.node_id,
                "title": node.title,
                "content": node.content,
                "node_type": node.node_type,
                "domain": node.domain,
                "properties": node.properties
            } for node in self.graph.nodes.values()],
            "relations": [{
                "relation_id": rel.relation_id,
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "relation_type": rel.relation_type,
                "weight": rel.weight
            } for rel in self.graph.relations]
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def save_graph(self, file_path: str) -> None:
        """保存知识图谱到文件"""
        json_str = self.export_to_json()
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(json_str)
        logger.info(f"知识图谱已保存: {file_path}")


def integrate_llm_wiki_to_graph(chunks: List[DocumentChunk], domain: str = "llm_wiki") -> KnowledgeGraph:
    """
    便捷函数：将 LLM Wiki 文档块集成到知识图谱
    
    Args:
        chunks: DocumentChunk 列表
        domain: 知识图谱域名
        
    Returns:
        KnowledgeGraph 实例
    """
    integrator = LLMWikiKnowledgeGraphIntegrator(domain=domain)
    return integrator.integrate_chunks(chunks)


def load_and_integrate_markdown(file_path: str, domain: str = "llm_wiki") -> KnowledgeGraph:
    """
    便捷函数：加载 Markdown 文件并集成到知识图谱
    
    Args:
        file_path: Markdown 文件路径
        domain: 知识图谱域名
        
    Returns:
        KnowledgeGraph 实例
    """
    from .parsers import LLMDocumentParser
    
    # 1. 解析 Markdown
    parser = LLMDocumentParser()
    chunks = parser.parse_markdown(file_path)
    
    if not chunks:
        logger.warning(f"未提取到任何块: {file_path}")
        return KnowledgeGraph()
    
    # 2. 集成到知识图谱
    return integrate_llm_wiki_to_graph(chunks, domain=domain)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("测试 LLM Wiki KnowledgeGraph 集成器")
    print("=" * 60)
    
    try:
        # 1. 创建测试 Markdown 文件
        print("\n1. 创建测试 Markdown 文件...")
        test_md = """# LLM Wiki 测试文档

## 介绍
这是一个用于测试 **KnowledgeGraph 集成** 的文档。

## API 接口
```python
def hello(name: str) -> str:
    \"\"\"问候函数\"\"\"
    return f"Hello, {name}!"
```

## 示例代码
```bash
echo "Hello, World!"
pip install livingtree
```

## 详细说明
这是一段详细说明文字，用于测试文本分块功能。

### 子章节 1
这是子章节的内容。

### 子章节 2
这是另一个子章节。
"""
        
        test_file = "./test_llm_doc.md"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_md)
        
        print(f"   ✅ 测试文件已创建: {test_file}")
        
        # 2. 加载并集成到知识图谱
        print("\n2. 加载并集成到知识图谱...")
        graph = load_and_integrate_markdown(test_file, domain="test_wiki")
        print(f"   ✅ 集成完成: {len(graph.nodes)} 个节点, {len(graph.relations)} 个关系")
        
        # 3. 查看统计信息
        print("\n3. 获取统计信息...")
        integrator = LLMWikiKnowledgeGraphIntegrator()
        integrator.graph = graph
        stats = integrator.get_statistics()
        print(f"   统计信息: {stats}")
        
        # 4. 搜索测试
        print("\n4. 搜索测试...")
        results = graph.search("KnowledgeGraph")
        print(f"   搜索结果: {len(results)} 个")
        for i, node in enumerate(results[:3], 1):
            print(f"   {i}. {node.title} ({node.node_type})")
        
        # 5. 导出 JSON
        print("\n5. 导出为 JSON...")
        json_str = integrator.export_to_json()
        print(f"   ✅ 导出完成: {len(json_str)} 字符")
        
        # 6. 清理测试文件
        print("\n6. 清理测试文件...")
        import os
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"   ✅ 测试文件已删除: {test_file}")
        
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
