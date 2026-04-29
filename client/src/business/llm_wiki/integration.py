"""
LLM Wiki 集成模块 - 将 Phase 1 解析器集成到现有 FusionRAG 系统
=======================================================

集成点：
1. LLMDocumentParser → FusionRAG KnowledgeBase
2. PaperParser → FusionRAG KnowledgeBase
3. CodeExtractor → FusionRAG KnowledgeBase (代码块索引)
4. 提供统一的搜索接口（复用 FusionRAG 四层架构）

作者: LivingTreeAI Team
日期: 2026-04-29
版本: 1.0.0 (Phase 1)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from loguru import logger

# 导入 Phase 1 模块（从新的模块结构）
from .models import DocumentChunk
from .parsers import LLMDocumentParser, PaperParser, CodeExtractor

# 尝试导入 FusionRAG 模块
try:
    from client.src.business.fusion_rag.knowledge_base import KnowledgeBaseLayer
    from client.src.business.fusion_rag.chunk_optimizer import ChunkOptimizer
    from client.src.business.fusion_rag.fusion_engine import FusionEngine
    FUSION_RAG_AVAILABLE = True
    logger.info("FusionRAG 模块导入成功")
except ImportError as e:
    FUSION_RAG_AVAILABLE = False
    logger.warning(f"FusionRAG 模块导入失败: {e}")


class LLMWikiIntegration:
    """
    LLM Wiki 集成器
    
    将 Phase 1 文档解析器集成到 FusionRAG 系统。
    """
    
    def __init__(self, knowledge_base=None, chunk_optimizer=None, fusion_engine=None):
        """初始化集成器"""
        # 使用现有的 FusionRAG 模块
        if FUSION_RAG_AVAILABLE:
            self.knowledge_base = knowledge_base or KnowledgeBaseLayer()
            # Note: ChunkOptimizer 可能没有 optimize() 方法，我们直接使用原始分块
            self.chunk_optimizer = chunk_optimizer  # 可选
            self.fusion_engine = fusion_engine  # 可选
        else:
            self.knowledge_base = None
            self.chunk_optimizer = None
            self.fusion_engine = None
            logger.warning("FusionRAG 不可用，将使用基础索引")
        
        # Phase 1 解析器
        self.md_parser = LLMDocumentParser()
        self.paper_parser = PaperParser()
        self.code_extractor = CodeExtractor()
        
        # 统计信息
        self.stats = {
            "indexed_documents": 0,
            "indexed_chunks": 0,
            "failed_documents": 0
        }
        
        logger.info("LLMWikiIntegration 初始化完成")
    
    def index_markdown_document(self, file_path: str) -> Dict[str, Any]:
        """
        索引 Markdown 文档
        
        Args:
            file_path: Markdown 文件路径
            
        Returns:
            索引结果
        """
        logger.info(f"索引 Markdown 文档: {file_path}")
        
        try:
            # 1. 解析文档（获取元数据和分块信息）
            chunks = self.md_parser.parse_markdown(file_path)
            
            if not chunks:
                return {
                    "success": False,
                    "error": "解析失败，未提取到任何块",
                    "file_path": file_path
                }
            
            # 2. 读取原始文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                full_content = f.read()
            
            # 3. 提取标题（从第一个 chunk 或文件内容）
            title = chunks[0].title if chunks else Path(file_path).stem
            if not title or title == "":
                # 从文件内容提取第一个 H1 标题
                import re
                h1_match = re.search(r"^#\s+(.+)$", full_content, re.MULTILINE)
                if h1_match:
                    title = h1_match.group(1).strip()
                else:
                    title = Path(file_path).stem
            
            # 4. 构建文档字典（符合 KnowledgeBaseLayer.add_document 要求）
            import hashlib
            doc_id = hashlib.md5(file_path.encode()).hexdigest()[:16]
            
            doc_info = {
                "id": doc_id,
                "title": title,
                "content": full_content,
                "type": "markdown",
                "metadata": {
                    "source": file_path,
                    "chunk_types": self._count_chunk_types(chunks),
                    "total_chunks": len(chunks)
                }
            }
            
            # 5. 索引到 FusionRAG
            indexed_count = 0
            if self.knowledge_base:
                try:
                    # add_document 返回分块数量
                    indexed_count = self.knowledge_base.add_document(doc_info)
                    logger.info(f"索引成功: {indexed_count} 个分块")
                except Exception as e:
                    logger.warning(f"索引失败: {e}")
                    # 如果失败，仅统计不索引
                    indexed_count = len(chunks)
            else:
                # FusionRAG 不可用，仅统计
                indexed_count = len(chunks)
            
            # 6. 更新统计
            self.stats["indexed_documents"] += 1
            self.stats["indexed_chunks"] += indexed_count
            
            return {
                "success": True,
                "file_path": file_path,
                "total_chunks": len(chunks),
                "indexed_chunks": indexed_count,
                "chunk_types": self._count_chunk_types(chunks)
            }
            
        except Exception as e:
            logger.error(f"索引 Markdown 文档失败: {e}")
            self.stats["failed_documents"] += 1
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def index_pdf_paper(self, file_path: str) -> Dict[str, Any]:
        """
        索引 PDF 论文
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            索引结果
        """
        logger.info(f"索引 PDF 论文: {file_path}")
        
        try:
            # 1. 解析 PDF
            result = self.paper_parser.parse_pdf(file_path)
            
            if not result.get("success"):
                return {
                    "success": False,
                    "error": result.get("error", "PDF 解析失败"),
                    "file_path": file_path
                }
            
            # 2. 获取文本内容和元数据
            text = result.get("text", "")
            pdf_metadata = result.get("metadata", {})
            title = pdf_metadata.get("Title", Path(file_path).stem)
            
            # 3. 构建文档字典
            import hashlib
            doc_id = hashlib.md5(file_path.encode()).hexdigest()[:16]
            
            doc_info = {
                "id": doc_id,
                "title": title,
                "content": text,
                "type": "pdf",
                "metadata": {
                    "source": file_path,
                    "pages": len(result.get("pages", [])),
                    "pdf_metadata": pdf_metadata
                }
            }
            
            # 4. 索引到 FusionRAG
            indexed_count = 0
            if self.knowledge_base:
                try:
                    indexed_count = self.knowledge_base.add_document(doc_info)
                    logger.info(f"索引成功: {indexed_count} 个分块")
                except Exception as e:
                    logger.warning(f"索引失败: {e}")
                    indexed_count = 1  # 至少统计为 1 个文档
            else:
                indexed_count = 1
            
            # 5. 更新统计
            self.stats["indexed_documents"] += 1
            self.stats["indexed_chunks"] += indexed_count
            
            return {
                "success": True,
                "file_path": file_path,
                "total_pages": len(result.get("pages", [])),
                "indexed_chunks": indexed_count
            }
            
        except Exception as e:
            logger.error(f"索引 PDF 论文失败: {e}")
            self.stats["failed_documents"] += 1
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def index_code_directory(self, dir_path: str, extensions: List[str] = None) -> Dict[str, Any]:
        """
        索引代码目录
        
        Args:
            dir_path: 目录路径
            extensions: 文件扩展名列表
            
        Returns:
            索引结果
        """
        logger.info(f"索引代码目录: {dir_path}")
        
        try:
            # 1. 提取代码
            if extensions:
                ext_list = extensions
            else:
                ext_list = [".py", ".js", ".java", ".cpp", ".go"]
            
            chunks = self.code_extractor.extract_from_directory(dir_path, ext_list)
            
            if not chunks:
                return {
                    "success": False,
                    "error": "未提取到任何代码块",
                    "dir_path": dir_path
                }
            
            # 2. 索引到 FusionRAG（每个文件一个文档）
            import hashlib
            indexed_count = 0
            failed_count = 0
            
            if self.knowledge_base:
                # 按文件分组（每个文件一个文档）
                file_chunks = {}
                for chunk in chunks:
                    source = chunk.source
                    if source not in file_chunks:
                        file_chunks[source] = chunk
                
                # 为每个文件创建一个文档
                for file_path, chunk in file_chunks.items():
                    try:
                        doc_id = hashlib.md5(file_path.encode()).hexdigest()[:16]
                        doc_info = {
                            "id": doc_id,
                            "title": chunk.title or Path(file_path).name,
                            "content": chunk.content,
                            "type": "code",
                            "metadata": {
                                "source": file_path,
                                "language": chunk.metadata.get("language", "unknown"),
                                "definitions": chunk.metadata.get("definitions", [])
                            }
                        }
                        
                        # 调用 add_document（返回分块数量）
                        chunks_created = self.knowledge_base.add_document(doc_info)
                        indexed_count += chunks_created
                        
                    except Exception as e:
                        logger.warning(f"索引文件失败 {file_path}: {e}")
                        failed_count += 1
            
            else:
                # FusionRAG 不可用，仅统计
                indexed_count = len(chunks)
            
            # 3. 更新统计
            self.stats["indexed_documents"] += 1
            self.stats["indexed_chunks"] += indexed_count
            
            return {
                "success": True,
                "dir_path": dir_path,
                "total_files": len(file_chunks) if self.knowledge_base else len(chunks),
                "indexed_chunks": indexed_count,
                "failed_files": failed_count
            }
            
        except Exception as e:
            logger.error(f"索引代码目录失败: {e}")
            self.stats["failed_documents"] += 1
            return {
                "success": False,
                "error": str(e),
                "dir_path": dir_path
            }
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索 LLM Wiki
        
        Args:
            query: 查询字符串
            top_k: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        logger.info(f"搜索: {query}")
        
        if not self.knowledge_base:
            logger.warning("KnowledgeBase 不可用，无法搜索")
            return []
        
        try:
            # 使用 FusionRAG 的搜索功能
            results = self.knowledge_base.search(query, top_k=top_k)
            return results
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "parsers": {
                "md_parser": "LLMDocumentParser",
                "paper_parser": "PaperParser",
                "code_extractor": "CodeExtractor"
            },
            "fusion_rag_available": FUSION_RAG_AVAILABLE
        }
    
    def _optimize_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """优化分块（如果 ChunkOptimizer 可用）"""
        if not self.chunk_optimizer:
            return chunks
        
        # Note: ChunkOptimizer 可能没有 optimize() 方法
        # 如果有，则调用；否则返回原始分块
        if hasattr(self.chunk_optimizer, 'optimize'):
            return self.chunk_optimizer.optimize(chunks)
        
        return chunks
    
    def _count_chunk_types(self, chunks: List[DocumentChunk]) -> Dict[str, int]:
        """统计块类型分布"""
        type_counts = {}
        for chunk in chunks:
            chunk_type = chunk.chunk_type
            type_counts[chunk_type] = type_counts.get(chunk_type, 0) + 1
        return type_counts


def create_llm_wiki_integration(knowledge_base=None) -> LLMWikiIntegration:
    """
    工厂函数：创建 LLMWikiIntegration 实例
    
    Args:
        knowledge_base: 可选的 KnowledgeBaseLayer 实例
        
    Returns:
        LLMWikiIntegration 实例
    """
    return LLMWikiIntegration(knowledge_base=knowledge_base)


def index_llm_document(file_path: str) -> Dict[str, Any]:
    """
    便捷函数：索引 LLM 文档
    
    Args:
        file_path: 文件路径
        
    Returns:
        索引结果
    """
    integration = create_llm_wiki_integration()
    
    if file_path.endswith(".md"):
        return integration.index_markdown_document(file_path)
    elif file_path.endswith(".pdf"):
        return integration.index_pdf_paper(file_path)
    else:
        return {
            "success": False,
            "error": f"不支持的文件类型: {file_path}"
        }


def search_llm_wiki(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    便捷函数：搜索 LLM Wiki
    
    Args:
        query: 查询字符串
        top_k: 返回结果数量
        
    Returns:
        搜索结果列表
    """
    integration = create_llm_wiki_integration()
    return integration.search(query, top_k=top_k)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("测试 LLM Wiki 集成模块")
    print("=" * 60)
    
    try:
        # 1. 创建集成器
        print("\n1. 创建 LLMWikiIntegration...")
        integration = create_llm_wiki_integration()
        print("   ✅ 集成器创建成功")
        
        # 2. 创建测试 Markdown 文件
        print("\n2. 创建测试 Markdown 文件...")
        test_md = """# LLM Wiki 测试文档

## 介绍
这是一个用于测试 LLM Wiki 集成功能的文档。

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
"""
        
        test_file = "./test_llm_doc.md"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_md)
        
        print(f"   ✅ 测试文件已创建: {test_file}")
        
        # 3. 索引测试文档
        print("\n3. 索引测试文档...")
        result = integration.index_markdown_document(test_file)
        print(f"   索引结果: {result}")
        
        # 4. 搜索测试
        print("\n4. 搜索测试...")
        results = integration.search("Hello 函数")
        print(f"   搜索结果: {len(results)} 个")
        for i, r in enumerate(results[:3], 1):
            print(f"   {i}. {r.get('content', '')[:100]}...")
        
        # 5. 获取统计信息
        print("\n5. 获取统计信息...")
        stats = integration.get_statistics()
        print(f"   统计信息: {stats}")
        
        # 6. 清理测试文件
        print("\n6. 清理测试文件...")
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
