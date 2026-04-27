"""
WebCrawlerTool - 网页爬虫工具（BaseTool 包装器）

将现有的 web_crawler 功能包装为标准的 BaseTool 子类
"""

from typing import Any, Dict, List, Optional
from loguru import logger

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from client.src.business.web_crawler.engine import ScraplingEngine, CrawlResult


class WebCrawlerTool(BaseTool):
    """
    网页爬虫工具
    
    爬取网页内容，支持 JavaScript 渲染、选择器提取。
    
    示例：
        tool = WebCrawlerTool()
        
        # 简单爬取
        result = tool.execute(url="https://example.com")
        
        # 使用选择器提取特定内容
        result = tool.execute(
            url="https://example.com",
            selector="h1",
            extract_type="text"
        )
    """
    
    def __init__(self, use_renderer: bool = False):
        """
        初始化网页爬虫工具
        
        Args:
            use_renderer: 是否使用 JavaScript 渲染（需要额外依赖）
        """
        super().__init__(
            name="web_crawler",
            description="网页爬虫工具，支持爬取网页内容、提取特定元素",
            category="web",
            tags=["web", "crawler", "scrape", "extract"],
            version="1.0.0"
        )
        self._engine = ScraplingEngine(use_renderer=use_renderer)
        self._logger = logger.bind(tool="WebCrawlerTool")
    
    def execute(
        self,
        url: str,
        selector: Optional[str] = None,
        extract_type: str = "text",
        timeout: int = 10
    ) -> ToolResult:
        """
        爬取网页
        
        Args:
            url: 目标 URL
            selector: 可选，CSS 选择器（如 "h1", ".content"）
            extract_type: 提取类型（"text", "html", "all"）
            timeout: 超时时间（秒）
            
        Returns:
            ToolResult 包含爬取结果
        """
        try:
            self._logger.info(f"爬取网页: {url}")
            
            # 调用现有的 ScraplingEngine
            crawl_result = self._engine.extract(
                url=url,
                selector=selector,
                extract_type=extract_type,
                timeout=timeout
            )
            
            # 转换为可序列化的字典
            result_data = {
                "url": crawl_result.url,
                "status": crawl_result.status,
                "success": crawl_result.success,
                "title": crawl_result.title,
                "content_length": len(crawl_result.content) if crawl_result.content else 0
            }
            
            # 添加内容（限制长度）
            if crawl_result.content:
                max_length = 5000
                content = crawl_result.content
                if len(content) > max_length:
                    content = content[:max_length] + "...(truncated)"
                result_data["content"] = content
            
            if not crawl_result.success:
                result_data["error"] = crawl_result.error
                return ToolResult(
                    success=False,
                    data=result_data,
                    error=crawl_result.error
                )
            
            self._logger.info(f"爬取成功: {url}, 状态码: {crawl_result.status}")
            
            return ToolResult.ok(
                data=result_data,
                message=f"成功爬取网页: {url}, 状态码: {crawl_result.status}"
            )
        
        except Exception as e:
            self._logger.exception(f"爬取网页失败: {url}")
            return ToolResult.fail(error=str(e))
    
    def batch_crawl(
        self,
        urls: List[str],
        selector: Optional[str] = None,
        extract_type: str = "text",
        timeout: int = 10
    ) -> ToolResult:
        """
        批量爬取网页
        
        Args:
            urls: URL 列表
            selector: 可选，CSS 选择器
            extract_type: 提取类型
            timeout: 超时时间（秒）
            
        Returns:
            ToolResult 包含批量爬取结果
        """
        try:
            self._logger.info(f"批量爬取 {len(urls)} 个网页")
            
            results = []
            success_count = 0
            
            for url in urls:
                result = self.execute(
                    url=url,
                    selector=selector,
                    extract_type=extract_type,
                    timeout=timeout
                )
                
                if result.success:
                    success_count += 1
                
                results.append({
                    "url": url,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error
                })
            
            return ToolResult.ok(
                data={
                    "total": len(urls),
                    "success_count": success_count,
                    "failed_count": len(urls) - success_count,
                    "results": results
                },
                message=f"批量爬取完成: {success_count}/{len(urls)} 成功"
            )
        
        except Exception as e:
            self._logger.exception("批量爬取失败")
            return ToolResult.fail(error=str(e))
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """获取工具定义（用于 LLM 调用）"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "目标网页 URL"
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS 选择器（可选），如 'h1', '.content'"
                    },
                    "extract_type": {
                        "type": "string",
                        "description": "提取类型",
                        "enum": ["text", "html", "all"],
                        "default": "text"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时时间（秒）",
                        "default": 10
                    }
                },
                "required": ["url"]
            }
        }


# 便捷函数
def crawl_webpage(
    url: str,
    selector: Optional[str] = None,
    extract_type: str = "text",
    timeout: int = 10
) -> ToolResult:
    """
    便捷函数：爬取网页
    
    Args:
        url: 目标 URL
        selector: CSS 选择器（可选）
        extract_type: 提取类型（"text", "html", "all"）
        timeout: 超时时间（秒）
        
    Returns:
        ToolResult 包含爬取结果
    """
    tool = WebCrawlerTool()
    return tool.execute(
        url=url,
        selector=selector,
        extract_type=extract_type,
        timeout=timeout
    )


if __name__ == "__main__":
    # 简单测试
    tool = WebCrawlerTool()
    
    # 测试爬取
    result = tool.execute(url="https://example.com")
    
    if result.success:
        print(f"[PASS] 爬取成功: {result.data['url']}")
        print(f"   状态码: {result.data['status']}")
        print(f"   标题: {result.data['title']}")
        print(f"   内容长度: {result.data['content_length']}")
    else:
        print(f"[FAIL] 爬取失败: {result.error}")


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
        _tool_instance = WebCrawlerTool()
        
        # 获取 ToolRegistry 单例
        from client.src.business.tools.tool_registry import ToolRegistry
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
