"""
文档 QA 系统

基于单个文档的提问和回答功能
"""

import os
import tempfile
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from langchain.llms import OpenAI, HuggingFacePipeline
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

from .document_processor import DocumentProcessor, DocumentChunk


def _get_openai_api_key() -> Optional[str]:
    """获取 OpenAI API Key（兼容统一配置）"""
    # 优先使用统一配置
    try:
        from core.config.unified_config import get_config
        key = get_config().get_api_key("openai")
        if key:
            return key
    except Exception:
        pass
    # 回退到环境变量
    return os.getenv("OPENAI_API_KEY")


@dataclass
class DocumentQAConfig:
    """文档 QA 配置"""
    embedding_model: str = "text-embedding-ada-002"
    llm_model: str = "gpt-4o"
    temperature: float = 0.7
    top_k: int = 3
    chunk_size: int = 1000
    chunk_overlap: int = 200


@dataclass
class DocumentQAResult:
    """文档 QA 结果"""
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float
    processing_time: float


class DocumentQA:
    """文档 QA 系统"""
    
    def __init__(self, config: Optional[DocumentQAConfig] = None):
        """
        初始化文档 QA 系统
        
        Args:
            config: 配置参数
        """
        self.config = config or DocumentQAConfig()
        self.document_processor = DocumentProcessor(
            embedding_model=self.config.embedding_model
        )
        self.vector_store = None
        self.qa_chain = None
        self.document_path = None
    
    def load_document(self, document_path: str) -> bool:
        """
        加载文档
        
        Args:
            document_path: 文档路径
            
        Returns:
            bool: 加载是否成功
        """
        try:
            # 处理文档
            if document_path.lower().endswith('.pdf'):
                chunks = self.document_processor.process_pdf(document_path)
            else:
                # 尝试作为文本文件处理
                with open(document_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                chunks = self.document_processor.process_text(text, source=document_path)
            
            # 创建向量存储
            self.vector_store = self.document_processor.create_vector_store(chunks)
            
            if self.vector_store:
                # 创建检索器
                retriever = self.vector_store.as_retriever(
                    search_kwargs={"k": self.config.top_k}
                )
                
                # 创建 LLM
                llm = self._get_llm()
                
                # 创建提示模板
                prompt = PromptTemplate(
                    template="""
                    你是一个基于文档的问答助手，你的任务是根据提供的文档内容回答问题。
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
                
                self.document_path = document_path
                return True
            
        except Exception as e:
            print(f"加载文档失败: {e}")
        
        return False
    
    def load_text(self, text: str, source: str = "text") -> bool:
        """
        加载文本
        
        Args:
            text: 文本内容
            source: 来源
            
        Returns:
            bool: 加载是否成功
        """
        try:
            # 处理文本
            chunks = self.document_processor.process_text(text, source=source)
            
            # 创建向量存储
            self.vector_store = self.document_processor.create_vector_store(chunks)
            
            if self.vector_store:
                # 创建检索器
                retriever = self.vector_store.as_retriever(
                    search_kwargs={"k": self.config.top_k}
                )
                
                # 创建 LLM
                llm = self._get_llm()
                
                # 创建提示模板
                prompt = PromptTemplate(
                    template="""
                    你是一个基于文档的问答助手，你的任务是根据提供的文档内容回答问题。
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
                
                self.document_path = source
                return True
            
        except Exception as e:
            print(f"加载文本失败: {e}")
        
        return False
    
    def _get_llm(self):
        """
        获取 LLM 实例
        
        Returns:
            LLM 实例
        """
        try:
            # 优先使用 OpenAI（通过统一配置）
            api_key = _get_openai_api_key()
            if api_key:
                return OpenAI(
                    model=self.config.llm_model,
                    temperature=self.config.temperature,
                    api_key=api_key
                )
        except Exception:
            pass
        
        # 回退到 HuggingFace
        try:
            from transformers import pipeline
            return HuggingFacePipeline(
                pipeline=pipeline(
                    "text-generation",
                    model="gpt2",
                    max_new_tokens=512,
                    temperature=self.config.temperature
                )
            )
        except Exception:
            pass
        
        # 最后回退到默认的 OpenAI
        return OpenAI(
            model="gpt-3.5-turbo-instruct",
            temperature=self.config.temperature
        )
    
    def query(self, question: str) -> Optional[DocumentQAResult]:
        """
        查询文档
        
        Args:
            question: 问题
            
        Returns:
            DocumentQAResult: 查询结果
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
            if "source_documents" in result:
                for doc in result["source_documents"]:
                    sources.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata
                    })
            
            # 计算处理时间
            processing_time = time.time() - start_time
            
            # 简单的置信度计算
            confidence = 0.8  # 这里可以根据实际情况调整
            
            return DocumentQAResult(
                answer=answer,
                sources=sources,
                confidence=confidence,
                processing_time=processing_time
            )
            
        except Exception as e:
            print(f"查询失败: {e}")
            return None
    
    def save_index(self, path: str):
        """
        保存索引
        
        Args:
            path: 保存路径
        """
        if self.vector_store:
            self.document_processor.save_vector_store(self.vector_store, path)
    
    def load_index(self, path: str):
        """
        加载索引
        
        Args:
            path: 加载路径
        """
        vector_store = self.document_processor.load_vector_store(path)
        if vector_store:
            self.vector_store = vector_store
            
            # 创建检索器
            retriever = self.vector_store.as_retriever(
                search_kwargs={"k": self.config.top_k}
            )
            
            # 创建 LLM
            llm = self._get_llm()
            
            # 创建提示模板
            prompt = PromptTemplate(
                template="""
                你是一个基于文档的问答助手，你的任务是根据提供的文档内容回答问题。
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
    
    def get_document_info(self) -> Dict[str, Any]:
        """
        获取文档信息
        
        Returns:
            Dict: 文档信息
        """
        return {
            "document_path": self.document_path,
            "vector_store": self.vector_store is not None,
            "qa_chain": self.qa_chain is not None
        }
