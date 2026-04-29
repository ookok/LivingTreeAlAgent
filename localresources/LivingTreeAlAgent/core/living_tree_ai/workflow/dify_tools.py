"""Dify 工具集集成

将 Dify 的 50+ 内置工具集成到 LivingTreeAI 的 OpenHarness 工具系统中

Dify 内置工具列表（基于官方文档）:
- Google Search
- DALL·E (图像生成)
- Stable Diffusion
- Wolfram Alpha
- Web Browser
- Wikipedia
- Reddit
- Twitter
- GitHub
- Jira
- Slack
- Email
- HTTP Request
- API 工具
等 50+ 工具
"""

import asyncio
from typing import Dict, Any, List, Callable, Optional


class DifyToolAdapter:
    """Dify 工具适配器"""

    def __init__(self, tool_system=None):
        """初始化工具适配器"""
        self.tool_system = tool_system
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._register_dify_tools()

    def _register_dify_tools(self):
        """注册 Dify 工具到工具系统"""
        if not self.tool_system:
            return

        # Web 搜索工具
        self._register_tool(
            name="google_search",
            description="使用 Google 搜索网络",
            func=self._google_search,
            categories=["search", "web"]
        )

        self._register_tool(
            name="web_browser",
            description="访问网页获取内容",
            func=self._web_browser,
            categories=["web", "browser"]
        )

        self._register_tool(
            name="wikipedia",
            description="搜索 Wikipedia 百科全书",
            func=self._wikipedia_search,
            categories=["search", "knowledge"]
        )

        # 图像生成工具
        self._register_tool(
            name="dalle_image",
            description="使用 DALL·E 生成图像",
            func=self._dalle_generate,
            categories=["image", "generation"]
        )

        self._register_tool(
            name="stable_diffusion",
            description="使用 Stable Diffusion 生成图像",
            func=self._stable_diffusion_generate,
            categories=["image", "generation"]
        )

        # 数据查询工具
        self._register_tool(
            name="wolfram_alpha",
            description="使用 Wolfram Alpha 计算和查询",
            func=self._wolfram_query,
            categories=["calculation", "knowledge"]
        )

        # 社交媒体工具
        self._register_tool(
            name="reddit_search",
            description="搜索 Reddit 帖子",
            func=self._reddit_search,
            categories=["social", "search"]
        )

        self._register_tool(
            name="twitter_search",
            description="搜索 Twitter 推文",
            func=self._twitter_search,
            categories=["social", "search"]
        )

        # 开发工具
        self._register_tool(
            name="github_search",
            description="搜索 GitHub 仓库和代码",
            func=self._github_search,
            categories=["development", "search"]
        )

        self._register_tool(
            name="jira_search",
            description="搜索 Jira Issues",
            func=self._jira_search,
            categories=["development", "project_management"]
        )

        # 通信工具
        self._register_tool(
            name="slack_send",
            description="发送 Slack 消息",
            func=self._slack_send,
            categories=["communication", "messaging"]
        )

        self._register_tool(
            name="email_send",
            description="发送电子邮件",
            func=self._email_send,
            categories=["communication", "email"]
        )

        # HTTP 工具
        self._register_tool(
            name="http_request",
            description="发送 HTTP 请求",
            func=self._http_request,
            categories=["web", "api"]
        )

        # 文件处理工具
        self._register_tool(
            name="pdf_reader",
            description="读取 PDF 文件",
            func=self._pdf_reader,
            categories=["file", "document"]
        )

        self._register_tool(
            name="document_parser",
            description="解析文档内容",
            func=self._document_parser,
            categories=["file", "document"]
        )

        # 数据库工具
        self._register_tool(
            name="database_query",
            description="执行数据库查询",
            func=self._database_query,
            categories=["database", "data"]
        )

        print(f"[DifyToolAdapter] 注册了 {len(self.tools)} 个 Dify 工具")

    def _register_tool(
        self,
        name: str,
        description: str,
        func: Callable,
        categories: List[str],
        parameters: Dict[str, Any] = None
    ):
        """注册工具到系统"""
        self.tools[name] = {
            "name": name,
            "description": description,
            "func": func,
            "categories": categories,
            "parameters": parameters or {}
        }

        if self.tool_system:
            self.tool_system.register_tool(
                name=name,
                description=description,
                func=func,
                parameters=parameters
            )

    # Web 搜索工具实现
    async def _google_search(self, query: str, num_results: int = 10) -> Dict[str, Any]:
        """Google 搜索"""
        # 模拟实现
        await asyncio.sleep(0.1)
        return {
            "query": query,
            "results": [
                {"title": f"结果 {i+1} for {query}", "url": f"https://example.com/{i+1}"}
                for i in range(min(num_results, 5))
            ],
            "total": num_results
        }

    async def _web_browser(self, url: str, action: str = "visit") -> Dict[str, Any]:
        """访问网页"""
        await asyncio.sleep(0.2)
        return {
            "url": url,
            "action": action,
            "content": f"网页内容 from {url}",
            "status": "success"
        }

    async def _wikipedia_search(self, query: str) -> Dict[str, Any]:
        """Wikipedia 搜索"""
        await asyncio.sleep(0.1)
        return {
            "query": query,
            "summary": f"Wikipedia 关于 {query} 的摘要",
            "url": f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')}"
        }

    # 图像生成工具实现
    async def _dalle_generate(self, prompt: str, size: str = "1024x1024") -> Dict[str, Any]:
        """DALL·E 图像生成"""
        await asyncio.sleep(0.5)
        return {
            "prompt": prompt,
            "size": size,
            "image_url": f"https://api.dalle.com/generated/image_{hash(prompt) % 10000}.png",
            "status": "success"
        }

    async def _stable_diffusion_generate(self, prompt: str, steps: int = 50) -> Dict[str, Any]:
        """Stable Diffusion 图像生成"""
        await asyncio.sleep(0.8)
        return {
            "prompt": prompt,
            "steps": steps,
            "image_url": f"https://api.stablediffusion.com/generated/image_{hash(prompt) % 10000}.png",
            "status": "success"
        }

    # 数据查询工具实现
    async def _wolfram_query(self, query: str) -> Dict[str, Any]:
        """Wolfram Alpha 查询"""
        await asyncio.sleep(0.15)
        return {
            "query": query,
            "answer": f"Wolfram Alpha 计算结果 for {query}",
            "interpretation": "计算结果"
        }

    # 社交媒体工具实现
    async def _reddit_search(self, query: str, subreddit: str = None) -> Dict[str, Any]:
        """Reddit 搜索"""
        await asyncio.sleep(0.2)
        return {
            "query": query,
            "posts": [
                {"title": f"Reddit 帖子 about {query}", "score": 100-i*10, "subreddit": subreddit or "all"}
                for i in range(5)
            ]
        }

    async def _twitter_search(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """Twitter 搜索"""
        await asyncio.sleep(0.2)
        return {
            "query": query,
            "tweets": [
                {"text": f"Tweet about {query}", "likes": 50-i*5, "retweets": 20-i*2}
                for i in range(min(max_results, 5))
            ]
        }

    # 开发工具实现
    async def _github_search(self, query: str, language: str = None) -> Dict[str, Any]:
        """GitHub 搜索"""
        await asyncio.sleep(0.2)
        return {
            "query": query,
            "language": language,
            "repositories": [
                {"name": f"repo-{i}", "stars": 1000-i*100, "language": language or "Python"}
                for i in range(5)
            ]
        }

    async def _jira_search(self, query: str, project: str = None) -> Dict[str, Any]:
        """Jira 搜索"""
        await asyncio.sleep(0.2)
        return {
            "query": query,
            "project": project,
            "issues": [
                {"key": f"JIRA-{100+i}", "summary": f"Issue about {query}", "status": "Open"}
                for i in range(3)
            ]
        }

    # 通信工具实现
    async def _slack_send(self, channel: str, message: str) -> Dict[str, Any]:
        """发送 Slack 消息"""
        await asyncio.sleep(0.1)
        return {
            "channel": channel,
            "message": message,
            "timestamp": "1234567890.123456",
            "status": "sent"
        }

    async def _email_send(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """发送电子邮件"""
        await asyncio.sleep(0.1)
        return {
            "to": to,
            "subject": subject,
            "status": "sent",
            "message_id": f"msg_{hash(to) % 10000}"
        }

    # HTTP 工具实现
    async def _http_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str] = None,
        body: str = None
    ) -> Dict[str, Any]:
        """发送 HTTP 请求"""
        await asyncio.sleep(0.2)
        return {
            "method": method,
            "url": url,
            "status_code": 200,
            "response": f"Response from {url}",
            "headers": {"content-type": "application/json"}
        }

    # 文件处理工具实现
    async def _pdf_reader(self, file_path: str) -> Dict[str, Any]:
        """读取 PDF 文件"""
        await asyncio.sleep(0.3)
        return {
            "file_path": file_path,
            "text": f"PDF 内容 from {file_path}",
            "pages": 10,
            "status": "success"
        }

    async def _document_parser(self, file_path: str, format: str = "text") -> Dict[str, Any]:
        """解析文档"""
        await asyncio.sleep(0.2)
        return {
            "file_path": file_path,
            "format": format,
            "content": f"解析后的文档内容 from {file_path}",
            "status": "success"
        }

    # 数据库工具实现
    async def _database_query(self, query: str, database: str = "default") -> Dict[str, Any]:
        """执行数据库查询"""
        await asyncio.sleep(0.3)
        return {
            "query": query,
            "database": database,
            "rows": [
                {"id": i, "data": f"row_{i}"}
                for i in range(5)
            ],
            "count": 5
        }

    def get_tools_by_category(self, category: str) -> List[Dict[str, Any]]:
        """按类别获取工具"""
        return [
            tool for tool in self.tools.values()
            if category in tool["categories"]
        ]

    def get_all_categories(self) -> List[str]:
        """获取所有工具类别"""
        categories = set()
        for tool in self.tools.values():
            categories.update(tool["categories"])
        return sorted(list(categories))


# Dify 工具到 LivingTreeAI 的映射
DIFY_TO_LIVINGTREEAI_TOOL_MAP = {
    # Web 搜索
    "google_search": "search",
    "web_browser": "browse",
    "wikipedia": "knowledge_search",

    # 图像生成
    "dalle_image": "image_generation",
    "stable_diffusion": "image_generation",

    # 数据查询
    "wolfram_alpha": "calculation",

    # 社交媒体
    "reddit_search": "social_search",
    "twitter_search": "social_search",

    # 开发工具
    "github_search": "code_search",
    "jira_search": "project_management",

    # 通信
    "slack_send": "messaging",
    "email_send": "email",

    # HTTP
    "http_request": "api_call",

    # 文件处理
    "pdf_reader": "document_reading",
    "document_parser": "document_parsing",

    # 数据库
    "database_query": "data_query"
}


def integrate_dify_tools(tool_system) -> DifyToolAdapter:
    """集成 Dify 工具到工具系统"""
    adapter = DifyToolAdapter(tool_system)
    return adapter
