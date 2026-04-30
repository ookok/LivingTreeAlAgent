"""
DeepSearchTool - 深度搜索工具（BaseTool 包装器）

将现有的 deep_search_wiki 功能包装为标准的 BaseTool 子类
"""

from typing import Any, Dict, List, Optional
from loguru import logger

from business.tools.base_tool import BaseTool
from business.tools.tool_result import ToolResult
from business.deep_search_wiki.wiki_generator import WikiGenerator, WikiPage
from business.deep_search_wiki.models import SearchResult, SourceInfo


class DeepSearchTool(BaseTool):
    """
    深度搜索工具
    
    基于多个信息源生成结构化的 Wiki 页面。
    
    示例：
        tool = DeepSearchTool()
        
        # 生成 Wiki
        result = tool.execute(topic="人工智能")
        
        # 使用自定义搜索结果
        result = tool.execute(
            topic="机器学习",
            use_search=True
        )
    """
    
    def __init__(self):
        super().__init__(
            name="deep_search",
            description="深度搜索工具，基于多个信息源生成结构化的 Wiki 页面",
            category="search",
            tags=["search", "wiki", "deep", "knowledge", "generation"],
            version="1.0.0"
        )
        self._generator = WikiGenerator()
        self._logger = logger.bind(tool="DeepSearchTool")
    
    def execute(
        self,
        topic: str,
        use_search: bool = True,
        max_sources: int = 10
    ) -> ToolResult:
        """
        执行深度搜索并生成 Wiki
        
        Args:
            topic: 搜索主题
            use_search: 是否使用搜索引擎（否则仅使用内置知识）
            max_sources: 最大源数量
            
        Returns:
            ToolResult 包含生成的 Wiki 页面
        """
        try:
            self._logger.info(f"深度搜索主题: {topic}")
            
            # 调用现有的 WikiGenerator
            wiki = self._generator.generate(
                topic=topic,
                use_search=use_search
            )
            
            # 转换为可序列化的字典
            result_data = {
                "topic": wiki.topic,
                "title": wiki.title,
                "section_count": len(wiki.sections),
                "source_count": len(wiki.sources),
                "sections": [
                    {
                        "title": section.title,
                        "level": section.level,
                        "content_preview": section.content[:200] + "..." if len(section.content) > 200 else section.content
                    }
                    for section in wiki.sections
                ],
                "sources": [
                    {
                        "title": source.title,
                        "url": source.url,
                        "source_type": source.source_type.value,
                        "credibility": source.credibility
                    }
                    for source in wiki.sources
                ]
            }
            
            # 添加完整内容（限制长度）
            full_content = wiki.to_markdown()
            if len(full_content) > 10000:
                full_content = full_content[:10000] + "\n\n...(truncated)"
            result_data["full_content"] = full_content
            
            self._logger.info(f"深度搜索完成: {wiki.topic}, {len(wiki.sections)} 个章节")
            
            return ToolResult.ok(
                data=result_data,
                message=f"成功生成深度搜索结果: {wiki.topic}, {len(wiki.sections)} 个章节"
            )
        
        except Exception as e:
            self._logger.exception(f"深度搜索失败: {topic}")
            return ToolResult.fail(error=str(e))
    
    def search_only(
        self,
        query: str,
        max_results: int = 10
    ) -> ToolResult:
        """
        仅执行搜索（不生成 Wiki）
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
            
        Returns:
            ToolResult 包含搜索结果
        """
        try:
            self._logger.info(f"执行搜索: {query}")
            
            # 调用搜索引擎
            search_results = self._generator.search_engine.search(
                query=query,
                max_results=max_results
            )
            
            # 转换为可序列化的字典
            results = [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "source_type": r.source_type.value if r.source_type else "unknown"
                }
                for r in search_results
            ]
            
            return ToolResult.ok(
                data={
                    "query": query,
                    "result_count": len(results),
                    "results": results
                },
                message=f"搜索完成: 找到 {len(results)} 个结果"
            )
        
        except Exception as e:
            self._logger.exception(f"搜索失败: {query}")
            return ToolResult.fail(error=str(e))
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """获取工具定义（用于 LLM 调用）"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "搜索主题或关键词"
                    },
                    "use_search": {
                        "type": "boolean",
                        "description": "是否使用搜索引擎（默认 True）",
                        "default": True
                    },
                    "max_sources": {
                        "type": "integer",
                        "description": "最大源数量（默认 10）",
                        "default": 10
                    }
                },
                "required": ["topic"]
            }
        }


# 便捷函数
def deep_search(
    topic: str,
    use_search: bool = True,
    max_sources: int = 10
) -> ToolResult:
    """
    便捷函数：深度搜索
    
    Args:
        topic: 搜索主题
        use_search: 是否使用搜索引擎
        max_sources: 最大源数量
        
    Returns:
        ToolResult 包含生成的 Wiki 页面
    """
    tool = DeepSearchTool()
    return tool.execute(
        topic=topic,
        use_search=use_search,
        max_sources=max_sources
    )


if __name__ == "__main__":
    # 简单测试
    tool = DeepSearchTool()
    
    # 测试深度搜索
    result = tool.execute(topic="人工智能")
    
    if result.success:
        print(f"[PASS] 深度搜索成功: {result.message}")
        print(f"   章节数: {result.data['section_count']}")
        print(f"   源数量: {result.data['source_count']}")
    else:
        print(f"[FAIL] 深度搜索失败: {result.error}")


# =============================================================================
# Auto-Registration
# =============================================================================

_registration_done = False

def _auto_register():
    """自动注册工具到 ToolRegistry"""
    global _registration_done
    
    if _registration_done:
        return
    
    try:
        # 创建工具实例
        _tool_instance = DeepSearchTool()
        
        # 获取 ToolRegistry 单例
        from business.tools.tool_registry import ToolRegistry
        _registry = ToolRegistry.get_instance()
        
        # 注册工具
        success = _registry.register_tool(_tool_instance)
        
        if success:
            import loguru
            loguru.logger.info(f"Auto-registered: {_tool_instance.name}")
        else:
            import loguru
            loguru.logger.warning(f"Auto-registration failed (tool already exists): {_tool_instance.name}")
        
        _registration_done = True
        
    except Exception as e:
        import loguru
        loguru.logger.error(f"Auto-registration error: {e}")


# 执行自动注册
_auto_register()
