"""
Hermes Tool Integration
将 PageIndex 集成到 Hermes Agent 作为 Tool

使用方式：
1. 在 Agent prompt 中添加能力说明
2. Agent 遇到文档问题时调用 query_manual tool
3. Tool 返回候选上下文
4. Agent 用上下文 + LLM 生成答案
"""

import asyncio
import os
from typing import Optional

from .index_builder import PageIndexBuilder
from .query_engine import QueryEngine

# 全局单例
_index_cache: dict[str, "PageIndexTool"] = {}


class PageIndexTool:
    """
    PageIndex Hermes Tool

    提供给 Agent 调用的工具
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        tree_height: int = 4
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tree_height = tree_height

        self.builder = PageIndexBuilder(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            tree_height=tree_height
        )
        self.query_engine = QueryEngine(self.builder)
        # 不再需要 OllamaClient，使用 GlobalModelRouter

    def build_index(
        self,
        file_path: str,
        doc_key: Optional[str] = None
    ) -> dict:
        """
        构建文档索引

        Args:
            file_path: 文档路径
            doc_key: 文档标识键

        Returns:
            dict: 构建结果
        """
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在: {file_path}"
            }

        try:
            doc = self.builder.build_index(
                file_path=file_path,
                doc_key=doc_key,
                use_llm_summaries=True  # 已迁移到 GlobalModelRouter
            )

            # 缓存到 query_engine
            self.query_engine.cache_index(doc_key or doc.title, doc)

            return {
                "success": True,
                "doc_id": doc.doc_id,
                "title": doc.title,
                "total_chunks": doc.total_chunks,
                "tree_height": doc.tree_height,
                "message": f"索引构建成功！共 {doc.total_chunks} 个 chunks"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def build_index_async(
        self,
        file_path: str,
        doc_key: Optional[str] = None
    ) -> dict:
        """异步构建索引"""
        return await asyncio.to_thread(self.build_index, file_path, doc_key)

    def query(
        self,
        question: str,
        doc_key: str,
        top_k: int = 3
    ) -> dict:
        """
        查询索引

        Args:
            question: 查询问题
            doc_key: 文档标识键
            top_k: 返回 top-k 结果

        Returns:
            dict: 查询结果
        """
        try:
            response = self.query_engine.query(
                question=question,
                doc_key=doc_key,
                top_k=top_k,
                use_tree_walk=True
            )

            if not response.results:
                return {
                    "success": True,
                    "answer": "在索引中未找到相关内容",
                    "context": "",
                    "candidates": [],
                    "response_time_ms": response.response_time_ms
                }

            # 构建上下文
            context_str = "\n\n".join([
                f"[Section {res.page_num}] {res.text[:800]}..."
                for res in response.results
            ])

            return {
                "success": True,
                "answer": None,  # Agent 需要用上下文 + LLM 生成
                "context": context_str,
                "candidates": [
                    {
                        "text": r.text[:500],
                        "page": r.page_num,
                        "score": r.score,
                        "section": r.section_title
                    }
                    for r in response.results
                ],
                "response_time_ms": response.response_time_ms
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def query_async(
        self,
        question: str,
        doc_key: str,
        top_k: int = 3
    ) -> dict:
        """异步查询"""
        return await asyncio.to_thread(self.query, question, doc_key, top_k)

    def generate_answer(
        self,
        question: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        使用 LLM 基于上下文生成答案（已迁移到 GlobalModelRouter）

        Args:
            question: 问题
            context: 上下文 (来自 query)
            system_prompt: 系统提示

        Returns:
            str: 生成的答案
        """
        if not context:
            return "抱歉，没有找到相关上下文来回答这个问题。"

        default_prompt = f"""你是一个专业的文档助手。请根据以下上下文回答用户的问题。

上下文：
{context}

问题: {question}

要求：
1. 只基于上下文中的信息回答
2. 如果上下文没有相关信息，诚实地说明"我没有找到相关信息"
3. 回答要准确、简洁
4. 如果涉及具体数据或步骤，请引用原文

回答:"""

        try:
            # 使用全局模型路由器（同步调用）
            from business.global_model_router import call_model_sync, ModelCapability

            response = call_model_sync(
                capability=ModelCapability.CHAT,
                prompt=system_prompt or default_prompt,
                system_prompt="你是一个专业的文档助手，只基于提供的上下文回答问题。"
            )

            return response.strip()

        except Exception as e:
            return f"生成答案时出错: {str(e)}"

    async def query_and_answer(
        self,
        question: str,
        doc_key: str,
        top_k: int = 3
    ) -> dict:
        """
        查询并生成答案 (完整流程)

        Args:
            question: 问题
            doc_key: 文档键
            top_k: 返回 top-k 结果

        Returns:
            dict: 包含答案和引用
        """
        # 1. 查询索引
        query_result = await self.query_async(question, doc_key, top_k)

        if not query_result.get("success"):
            return query_result

        # 2. 生成答案
        if query_result.get("context"):
            answer = self.generate_answer(question, query_result["context"])
        else:
            answer = "在索引中未找到相关内容"

        # 3. 构建引用
        citations = []
        for candidate in query_result.get("candidates", []):
            citations.append(
                f"第{candidate['page']}页 (相关度: {candidate['score']:.2f})"
            )

        return {
            "success": True,
            "answer": answer,
            "citations": citations,
            "candidates": query_result.get("candidates", []),
            "response_time_ms": query_result.get("response_time_ms", 0)
        }

    def list_documents(self) -> list[dict]:
        """列出所有已索引的文档"""
        return self.builder.list_documents()

    def get_stats(self) -> dict:
        """获取索引统计"""
        return self.builder.get_stats().to_dict()

    def is_indexed(self, doc_key: str = None) -> bool:
        """检查是否有已索引的文档"""
        if doc_key:
            return self.query_engine.has_index(doc_key)
        return len(self.query_engine._cache) > 0


def get_pageindex_tool(
    doc_key: str = "default",
    **kwargs
) -> PageIndexTool:
    """
    获取 PageIndexTool 单例

    Args:
        doc_key: 文档键
        **kwargs: 传给 PageIndexTool 的参数

    Returns:
        PageIndexTool: 工具实例
    """
    if doc_key not in _index_cache:
        _index_cache[doc_key] = PageIndexTool(**kwargs)
    return _index_cache[doc_key]


def register_pageindex_tools(registry) -> list[dict]:
    """
    向 Hermes Tool Registry 注册 PageIndex 工具

    Args:
        registry: Hermes 的 tools_registry

    Returns:
        list[dict]: 注册的工具列表
    """
    tools = [
        {
            "name": "query_manual",
            "description": "在已索引的技术手册/文档里查找最相关的章节/段落。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "要查询的问题"
                    },
                    "doc_key": {
                        "type": "string",
                        "description": "文档标识键 (默认: default_manual)"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回 top-k 结果 (默认: 3)",
                        "default": 3
                    }
                },
                "required": ["question", "doc_key"]
            },
            "handler": "pageindex_query"
        },
        {
            "name": "build_manual_index",
            "description": "为技术手册/PDF 等文档构建 PageIndex 索引。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文档文件路径"
                    },
                    "doc_key": {
                        "type": "string",
                        "description": "文档标识键 (默认用文件名)"
                    }
                },
                "required": ["file_path"]
            },
            "handler": "pageindex_build"
        },
        {
            "name": "list_indexed_documents",
            "description": "列出所有已索引的文档。",
            "parameters": {
                "type": "object",
                "properties": {}
            },
            "handler": "pageindex_list"
        }
    ]

    # 注册到 registry
    for tool in tools:
        registry.register(
            name=tool["name"],
            description=tool["description"],
            parameters=tool["parameters"],
            handler=tool["handler"]
        )

    return tools
