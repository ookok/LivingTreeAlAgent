"""
多文档问答系统

支持多个文档的加载、检索和问答
"""

import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from .document_processor import DocumentProcessor, DocumentChunk


@dataclass
class DocumentInfo:
    """文档信息"""
    id: str
    name: str
    path: str
    type: str
    chunk_count: int


@dataclass
class MultiDocQAResult:
    """多文档 QA 结果"""
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float
    processing_time: float
    documents: List[DocumentInfo]


class MultiDocumentQA:
    """多文档问答系统"""
    
    def __init__(
        self,
        embedding_model: str = "text-embedding-ada-002",
        llm_model: str = "gpt-4o",
        temperature: float = 0.7,
        top_k: int = 3,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        初始化多文档问答系统
        
        Args:
            embedding_model: 嵌入模型
            llm_model: LLM 模型
            temperature: 温度参数
            top_k: 检索的 top k 结果
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
        """
        self.document_processor = DocumentProcessor(
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        self.llm_model = llm_model
        self.temperature = temperature
        self.top_k = top_k
        
        self.vector_store = None
        self.documents: List[DocumentInfo] = []
        self.qa_chain = None
    
    def load_document(self, file_path: str) -> bool:
        """
        加载单个文档
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 加载是否成功
        """
        try:
            # 处理文档
            chunks = self.document_processor.process_file(file_path)
            
            if not chunks:
                print(f"[MultiDocumentQA] 无法处理文档: {file_path}")
                return False
            
            # 创建向量存储
            if self.vector_store is None:
                self.vector_store = self.document_processor.create_vector_store(chunks)
            else:
                # 合并到现有向量存储
                new_store = self.document_processor.create_vector_store(chunks)
                self.vector_store.merge_from(new_store)
            
            # 记录文档信息
            doc_info = DocumentInfo(
                id=f"doc_{len(self.documents)}",
                name=os.path.basename(file_path),
                path=file_path,
                type=os.path.splitext(file_path)[1].lower(),
                chunk_count=len(chunks)
            )
            self.documents.append(doc_info)
            
            # 重建 QA 链
            self._rebuild_qa_chain()
            
            return True
            
        except Exception as e:
            print(f"[MultiDocumentQA] 加载文档失败: {e}")
            return False
    
    def load_documents(self, file_paths: List[str]) -> int:
        """
        批量加载文档
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            int: 成功加载的文档数量
        """
        success_count = 0
        
        for file_path in file_paths:
            if self.load_document(file_path):
                success_count += 1
        
        return success_count
    
    def remove_document(self, doc_id: str) -> bool:
        """
        移除文档
        
        Args:
            doc_id: 文档 ID
            
        Returns:
            bool: 移除是否成功
        """
        try:
            # 找到文档
            doc_info = None
            for doc in self.documents:
                if doc.id == doc_id:
                    doc_info = doc
                    break
            
            if not doc_info:
                return False
            
            # 注意：FAISS 不支持直接删除，需要重建
            # 这里简化处理，实际应用中可以考虑重新加载其他文档
            
            self.documents.remove(doc_info)
            
            # 重建向量存储（排除被删除的文档）
            # 由于实现复杂性，这里只移除文档信息
            # 完整实现需要维护文档到 chunks 的映射
            
            self._rebuild_qa_chain()
            
            return True
            
        except Exception as e:
            print(f"[MultiDocumentQA] 移除文档失败: {e}")
            return False
    
    def _rebuild_qa_chain(self):
        """重建 QA 链"""
        if not self.vector_store:
            return
        
        try:
            from langchain.llms import OpenAI
            from langchain.chains import RetrievalQA
            from langchain.prompts import PromptTemplate
            
            # 创建检索器
            retriever = self.vector_store.as_retriever(
                search_kwargs={"k": self.top_k}
            )
            
            # 创建 LLM
            llm = OpenAI(
                model=self.llm_model,
                temperature=self.temperature
            )
            
            # 创建提示模板
            prompt = PromptTemplate(
                template="""
你是一个基于多个文档的问答助手，你的任务是根据提供的文档内容回答问题。
请严格基于文档内容回答，不要添加文档中没有的信息。
如果文档中没有相关信息，请明确说明。

文档内容：
{context}

问题：
{question}

回答：
""",
                input_variables=["context", "question"]
            )
            
            # 创建 QA 链
            self.qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",
                retriever=retriever,
                return_source_documents=True,
                chain_type_kwargs={"prompt": prompt}
            )
            
        except Exception as e:
            print(f"[MultiDocumentQA] 重建 QA 链失败: {e}")
    
    def query(self, question: str) -> Optional[MultiDocQAResult]:
        """
        查询
        
        Args:
            question: 问题
            
        Returns:
            MultiDocQAResult: 查询结果
        """
        import time
        
        if not self.qa_chain:
            return None
        
        start_time = time.time()
        
        try:
            # 执行查询
            result = self.qa_chain({
                "query": question
            })
            
            # 提取答案
            answer = result.get("result", "")
            
            # 提取源文档
            sources = []
            doc_ids = set()
            
            if "source_documents" in result:
                for doc in result["source_documents"]:
                    source = {
                        "content": doc.page_content,
                        "metadata": doc.metadata
                    }
                    sources.append(source)
                    
                    # 提取文档 ID
                    if "source" in doc.metadata:
                        for doc_info in self.documents:
                            if doc_info.path == doc.metadata["source"]:
                                doc_ids.add(doc_info.id)
                                break
            
            # 计算处理时间
            processing_time = time.time() - start_time
            
            # 获取涉及的文档
            involved_docs = [doc for doc in self.documents if doc.id in doc_ids]
            
            # 简单的置信度计算
            confidence = 0.8
            
            return MultiDocQAResult(
                answer=answer,
                sources=sources,
                confidence=confidence,
                processing_time=processing_time,
                documents=involved_docs
            )
            
        except Exception as e:
            print(f"[MultiDocumentQA] 查询失败: {e}")
            return None
    
    def get_documents(self) -> List[DocumentInfo]:
        """获取已加载的文档列表"""
        return self.documents
    
    def clear(self):
        """清空所有文档"""
        self.vector_store = None
        self.documents = []
        self.qa_chain = None
    
    def save_index(self, path: str):
        """
        保存索引
        
        Args:
            path: 保存路径
        """
        if self.vector_store:
            self.document_processor.save_vector_store(self.vector_store, path)
    
    def load_index(self, path: str) -> bool:
        """
        加载索引
        
        Args:
            path: 加载路径
            
        Returns:
            bool: 加载是否成功
        """
        try:
            vector_store = self.document_processor.load_vector_store(path)
            if vector_store:
                self.vector_store = vector_store
                self._rebuild_qa_chain()
                return True
            return False
        except Exception as e:
            print(f"[MultiDocumentQA] 加载索引失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_chunks = sum(doc.chunk_count for doc in self.documents)
        
        return {
            "document_count": len(self.documents),
            "total_chunks": total_chunks,
            "documents": [
                {
                    "id": doc.id,
                    "name": doc.name,
                    "type": doc.type,
                    "chunk_count": doc.chunk_count
                }
                for doc in self.documents
            ]
        }


class DocumentCollection:
    """文档集合管理器"""
    
    def __init__(self):
        self.collections: Dict[str, MultiDocumentQA] = {}
    
    def create_collection(self, name: str, **kwargs) -> MultiDocumentQA:
        """
        创建文档集合
        
        Args:
            name: 集合名称
            **kwargs: 传递给 MultiDocumentQA 的参数
            
        Returns:
            MultiDocumentQA: 多文档问答实例
        """
        if name in self.collections:
            return self.collections[name]
        
        qa = MultiDocumentQA(**kwargs)
        self.collections[name] = qa
        return qa
    
    def get_collection(self, name: str) -> Optional[MultiDocumentQA]:
        """
        获取文档集合
        
        Args:
            name: 集合名称
            
        Returns:
            MultiDocumentQA 或 None
        """
        return self.collections.get(name)
    
    def delete_collection(self, name: str) -> bool:
        """
        删除文档集合
        
        Args:
            name: 集合名称
            
        Returns:
            bool: 删除是否成功
        """
        if name in self.collections:
            del self.collections[name]
            return True
        return False
    
    def list_collections(self) -> List[str]:
        """列出所有集合"""
        return list(self.collections.keys())


# 全局文档集合管理器
_collection_manager: Optional[DocumentCollection] = None


def get_collection_manager() -> DocumentCollection:
    """获取文档集合管理器"""
    global _collection_manager
    if _collection_manager is None:
        _collection_manager = DocumentCollection()
    return _collection_manager
