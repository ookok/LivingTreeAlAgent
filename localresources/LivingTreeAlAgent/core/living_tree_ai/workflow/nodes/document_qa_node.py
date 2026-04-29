"""
文档 QA 工作流节点

将文档问答功能集成到工作流系统中
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from ..workflow import WorkflowNode, StepStatus


@dataclass
class DocumentQANode(WorkflowNode):
    """文档问答节点"""
    
    node_type: str = "document_qa"
    collection_name: str = "default"
    question_variable: str = "question"
    result_variable: str = "qa_result"
    
    def __post_init__(self):
        if not self.name:
            self.name = "文档问答"
        if not self.description:
            self.description = "基于文档的问答"
        if not self.icon:
            self.icon = "📄"
        if not self.color:
            self.color = "#8b5cf6"
        
        self.available_actions = ["complete"]
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from ..knowledge.multi_document_qa import get_collection_manager
            
            manager = get_collection_manager()
            qa = manager.get_collection(self.collection_name)
            
            if not qa:
                return {
                    "status": StepStatus.FAILED.value,
                    "error": f"文档集合不存在: {self.collection_name}"
                }
            
            question = context.get(self.question_variable, "")
            if not question:
                return {
                    "status": StepStatus.FAILED.value,
                    "error": "问题不能为空"
                }
            
            result = qa.query(question)
            
            if not result:
                return {
                    "status": StepStatus.FAILED.value,
                    "error": "问答执行失败"
                }
            
            if self.result_variable:
                context[self.result_variable] = {
                    "answer": result.answer,
                    "sources": [
                        {
                            "content": s["content"][:200] + "..." if len(s["content"]) > 200 else s["content"],
                            "metadata": s["metadata"]
                        }
                        for s in result.sources
                    ],
                    "confidence": result.confidence,
                    "processing_time": result.processing_time,
                    "documents": [
                        {
                            "id": d.id,
                            "name": d.name,
                            "type": d.type
                        }
                        for d in result.documents
                    ]
                }
            
            return {
                "status": StepStatus.COMPLETED.value,
                "result": result.answer
            }
            
        except Exception as e:
            return {
                "status": StepStatus.FAILED.value,
                "error": str(e)
            }
    
    def validate(self) -> Dict[str, Any]:
        errors = []
        if not self.collection_name:
            errors.append("文档集合名称不能为空")
        if not self.question_variable:
            errors.append("问题变量名不能为空")
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }


@dataclass
class DocumentLoaderNode(WorkflowNode):
    """文档加载节点"""
    
    node_type: str = "document_loader"
    collection_name: str = "default"
    file_path_variable: str = "file_path"
    result_variable: str = "load_result"
    
    def __post_init__(self):
        if not self.name:
            self.name = "文档加载"
        if not self.description:
            self.description = "加载文档到问答系统"
        if not self.icon:
            self.icon = "📥"
        if not self.color:
            self.color = "#10b981"
        
        self.available_actions = ["complete"]
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from ..knowledge.multi_document_qa import get_collection_manager
            
            manager = get_collection_manager()
            qa = manager.get_collection(self.collection_name)
            
            if not qa:
                qa = manager.create_collection(self.collection_name)
            
            file_path = context.get(self.file_path_variable, "")
            if not file_path:
                return {
                    "status": StepStatus.FAILED.value,
                    "error": "文件路径不能为空"
                }
            
            success = qa.load_document(file_path)
            
            if not success:
                return {
                    "status": StepStatus.FAILED.value,
                    "error": f"加载文档失败: {file_path}"
                }
            
            stats = qa.get_stats()
            
            if self.result_variable:
                context[self.result_variable] = {
                    "success": True,
                    "file_path": file_path,
                    "document_count": stats["document_count"],
                    "total_chunks": stats["total_chunks"]
                }
            
            return {
                "status": StepStatus.COMPLETED.value,
                "result": f"成功加载文档: {file_path}"
            }
            
        except Exception as e:
            return {
                "status": StepStatus.FAILED.value,
                "error": str(e)
            }
    
    def validate(self) -> Dict[str, Any]:
        errors = []
        if not self.collection_name:
            errors.append("文档集合名称不能为空")
        if not self.file_path_variable:
            errors.append("文件路径变量名不能为空")
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }


def create_document_qa_node(
    name: str = "文档问答",
    collection_name: str = "default",
    question_variable: str = "question",
    result_variable: str = "qa_result"
) -> DocumentQANode:
    return DocumentQANode(
        name=name,
        collection_name=collection_name,
        question_variable=question_variable,
        result_variable=result_variable
    )


def create_document_loader_node(
    name: str = "文档加载",
    collection_name: str = "default",
    file_path_variable: str = "file_path",
    result_variable: str = "load_result"
) -> DocumentLoaderNode:
    return DocumentLoaderNode(
        name=name,
        collection_name=collection_name,
        file_path_variable=file_path_variable,
        result_variable=result_variable
    )
